"""Core HTTP proxy server with sequential provider failover and SSE passthrough.

Architecture::

    Client ──POST──→ local-gateway ──try DeepSeek──→ api.deepseek.com
                                     └ fail → try KIMI ──→ api.moonshot.cn
                                                 └ fail → 502

For stream=true (SSE), the proxy connects to each provider **before**
sending HTTP 200 to the client.  This means the client never sees a
partial response — if the first provider fails, the second is tried
transparently.  Only after a provider confirms HTTP 200 does the proxy
commit to the client.
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from local_gateway.providers import load_providers, resolve_model

log = logging.getLogger("local-gateway")

# ── Defaults ───────────────────────────────────────────────────────────
DEFAULT_PORT = 18790
DEFAULT_HOST = "127.0.0.1"


class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP request handler with sequential provider failover.

    The critical design invariant: the proxy connects to the upstream
    provider *before* sending HTTP 200 headers to the client.  If the
    upstream returns 4xx/5xx or fails to connect, the next provider is
    tried silently.  The client only sees a response once a provider
    has confirmed it can serve the request.

    For streaming (SSE), chunks are forwarded in 4 KiB blocks.
    """

    providers: list[dict] = []
    provider_order: list[str] = []

    # ── CORS ──────────────────────────────────────────────────────────
    def do_OPTIONS(self):
        self._cors_headers()
        self._respond(204, b"")

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    # ── Health ────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/health":
            self._cors_headers()
            status = {
                "status": "ok",
                "providers": list(self.provider_order),
                "model_mappings": len(self._get_model_map()),
            }
            self._respond(200, json.dumps(status).encode())
            return
        if self.path == "/v1/models":
            self._handle_models()
            return
        self._respond(404, json.dumps({"error": "not found"}).encode())

    def _handle_models(self):
        """Return available models from all configured providers."""
        models = []
        for name in self.provider_order:
            p = self._get_provider(name)
            if p:
                models.append({
                    "id": p["default_model"],
                    "provider": name,
                    "object": "model",
                })
        self._cors_headers()
        self._respond(200, json.dumps({"object": "list", "data": models}).encode())

    # ── POST (chat completions) ───────────────────────────────────────
    def do_POST(self):
        self._cors_headers()
        content_length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            req = json.loads(body)
        except json.JSONDecodeError as e:
            self._respond(400, json.dumps({
                "error": {"message": f"Invalid JSON: {e}", "type": "invalid_request_error"},
            }).encode())
            return

        is_stream = req.get("stream", False)
        original_model = req.get("model", "")

        # Try each provider in order
        last_error = None
        for idx, provider_name in enumerate(self.provider_order):
            provider = self._get_provider(provider_name)
            if provider is None:
                continue

            # Resolve model name for this provider
            if idx == 0:
                model = original_model or provider["default_model"]
            else:
                model = resolve_model(
                    original_model or provider["default_model"],
                    from_provider=self.provider_order[0],
                    to_provider=provider_name,
                )

            # Build request
            payload = dict(req)
            payload["model"] = model
            payload.setdefault("max_tokens", 4096)

            url = f"{provider['base_url'].rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {provider['api_key']}",
                "User-Agent": "local-gateway/0.1.0",
            }
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

            try:
                upstream_req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                upstream = urllib.request.urlopen(upstream_req, timeout=120)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")[:300]
                log.warning("FAIL %s — HTTP %d: %s", provider_name, e.code, err_body)
                last_error = {"provider": provider_name, "status": e.code, "detail": err_body}
                continue
            except urllib.error.URLError as e:
                log.warning("FAIL %s — connection: %s", provider_name, e.reason)
                last_error = {"provider": provider_name, "status": 0, "detail": str(e.reason)}
                continue
            except Exception as e:
                log.warning("FAIL %s — %s: %s", provider_name, type(e).__name__, e)
                last_error = {"provider": provider_name, "status": 0, "detail": f"{type(e).__name__}: {e}"}
                continue

            # ── Connected — forward response ──────────────────────
            if is_stream:
                self._forward_stream(provider_name, upstream)
            else:
                self._forward_sync(provider_name, upstream)
            return

        # ── All providers failed ──────────────────────────────────
        log.error("ALL PROVIDERS FAILED — last: %s", last_error)
        self._respond(502, json.dumps({
            "error": {
                "message": f"All providers failed. Last: {last_error['provider']} "
                           f"(HTTP {last_error['status']})" if last_error else "No providers configured",
                "type": "upstream_error",
                "detail": last_error,
            }
        }).encode())

    def _forward_sync(self, provider_name: str, upstream):
        """Forward a non-streaming response (read fully, then send)."""
        try:
            resp_body = upstream.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
        except Exception as e:
            log.error("Error forwarding sync response from %s: %s", provider_name, e)
            return
        finally:
            upstream.close()
        log.info("200 %s (sync) — %d bytes", provider_name, len(resp_body))

    def _forward_stream(self, provider_name: str, upstream):
        """Forward an SSE stream chunk-by-chunk."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.flush()

        chunks = 0
        try:
            while True:
                chunk = upstream.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                chunks += 1
        except (socket.error, BrokenPipeError, ConnectionResetError):
            log.info("Stream cut short by client during %s", provider_name)
        except Exception as e:
            log.error("Stream error from %s: %s", provider_name, e)
        finally:
            upstream.close()
        log.info("200 %s (stream) — %d chunks", provider_name, chunks)

    # ── Helpers ───────────────────────────────────────────────────────
    def _get_provider(self, name: str) -> Optional[dict]:
        for p in self.providers:
            if p["name"] == name:
                return p
        return None

    def _get_model_map(self):
        """Return active model mappings for display."""
        from local_gateway.providers import MODEL_MAP
        return dict(MODEL_MAP)

    def _respond(self, status: int, body: bytes, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def log_message(self, fmt, *args):
        log.info("<= %s %s", self.client_address[0], fmt % args)


# ── Server factory ─────────────────────────────────────────────────────

def create_server(
    providers: list[dict],
    provider_order: list[str],
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> HTTPServer:
    """Create a configured HTTPServer ready to serve."""
    handler = ProxyHandler
    handler.providers = providers
    handler.provider_order = provider_order
    server = HTTPServer((host, port), handler)
    return server


def run_server(
    providers: list[dict],
    provider_order: list[str],
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
):
    """Start the proxy server (blocking)."""
    server = create_server(providers, provider_order, host, port)
    log.info("=" * 55)
    log.info("  LocalGateway")
    log.info("  listening on http://%s:%d", host, port)
    log.info("  providers: %s", ", ".join(provider_order))
    log.info("  streaming: supported (SSE passthrough)")
    log.info("  endpoints: POST /v1/chat/completions")
    log.info("             GET  /health")
    log.info("             GET  /v1/models")
    log.info("=" * 55)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutdown")
        server.server_close()
