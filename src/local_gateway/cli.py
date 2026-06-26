"""Command-line interface for local-gateway.

Usage::

    local-gateway --providers deepseek,kimi
    local-gateway --providers deepseek,kimi,openai --port 8080 --host 0.0.0.0
    local-gateway --providers deepseek,kimi --api-key deepseek=sk-xxx --api-key kimi=sk-yyy
    local-gateway --list-models
"""

from __future__ import annotations

import argparse
import logging
import sys

from local_gateway import __version__
from local_gateway.providers import load_providers, dump_mapping_table, BUILTIN_PROVIDERS
from local_gateway.proxy import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="local-gateway",
        description="Desktop LLM gateway — multi-provider failover with model name mapping",
    )
    parser.add_argument(
        "--providers", "-p",
        help="Comma-separated provider names in failover order (e.g. deepseek,kimi,openai)",
        default="",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=18790,
        help="Listen port (default: 18790)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Listen host (default: 127.0.0.1). Use 0.0.0.0 for all interfaces",
    )
    parser.add_argument(
        "--api-key",
        action="append",
        help="Provider API key (can be repeated): --api-key deepseek=sk-xxx",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all built-in providers and exit",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Show cross-provider model name mapping table and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"local-gateway {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # ── Logging ─────────────────────────────────────────────────────
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("local-gateway")

    # ── Info-only flags ─────────────────────────────────────────────
    if args.list_providers:
        print("Built-in providers:")
        for name, spec in sorted(BUILTIN_PROVIDERS.items()):
            print(f"  {name:15s}  {spec['base_url']}")
            print(f"                  env: {spec['env_key']}")
            print(f"                  default model: {spec['default_model']}")
            print()
        return 0

    if args.list_models:
        print(dump_mapping_table())
        return 0

    # ── Validate ────────────────────────────────────────────────────
    if not args.providers:
        parser.print_help()
        print("\nError: --providers is required (e.g. --providers deepseek,kimi)")
        return 1

    provider_names = [p.strip() for p in args.providers.split(",") if p.strip()]
    if len(provider_names) < 1:
        print("Error: at least one provider is required")
        return 1

    # ── Parse --api-key overrides ───────────────────────────────────
    api_keys = {}
    if args.api_key:
        for kv in args.api_key:
            if "=" not in kv:
                print(f"Warning: ignoring malformed --api-key '{kv}' (expected name=key)")
                continue
            name, key = kv.split("=", 1)
            api_keys[name.strip()] = key.strip()

    # ── Load providers ──────────────────────────────────────────────
    try:
        providers = load_providers(provider_names, api_keys=api_keys)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    # ── Start server ────────────────────────────────────────────────
    log.info("LocalGateway v%s starting", __version__)
    log.info("Provider order: %s", " → ".join(provider_names))

    try:
        run_server(providers, provider_names, host=args.host, port=args.port)
    except OSError as e:
        log.error("Cannot start server: %s", e)
        return 1
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
