# LocalGateway

**Desktop LLM gateway with multi-provider failover and automatic model name mapping.**

> 💙 **Support LocalGateway**
> If this saved you from an API outage, consider [sponsoring us](https://github.com/sponsors/Correctover).
> - ☕ **$5/month** — Thanks + priority issue responses
> - 🚀 **$29/month** — Private Discord + monthly update briefings
> - 🏢 **$99/month** — Enterprise sponsor, logo on README

```
pip install local-gateway
```

```bash
# Set your API keys
export DEEPSEEK_API_KEY=sk-...
export KIMI_API_KEY=sk-...

# Start the gateway
local-gateway --providers deepseek,kimi
```

## Why?

Every desktop AI tool (Cursor, Claude Desktop, Windsurf, Continue.dev) lets you configure **one** API endpoint. If that provider goes down, your tool stops working.

LocalGateway is a lightweight proxy that sits between your desktop tools and LLM providers. It tries providers in sequence — if the first one fails, it **automatically falls back** to the next.

## The Model Name Problem

Model names are not portable across providers:

| Your Request | DeepSeek | KIMI |
|-------------|----------|------|
| `deepseek-chat` | ✅ works | ❌ 404 — KIMI doesn't know this name |
| `gpt-4o` | ❌ doesn't exist | ❌ doesn't exist |

LocalGateway solves this with a **cross-provider model name mapping table**. When falling back from DeepSeek to KIMI, it automatically maps `deepseek-chat → moonshot-v1-128k`.

## Usage

```bash
# Two providers (DeepSeek → KIMI auto-failover)
local-gateway --providers deepseek,kimi

# Three providers
local-gateway --providers deepseek,kimi,openai

# Custom port
local-gateway --providers deepseek,kimi --port 8080

# Explicit API keys (instead of env vars)
local-gateway --providers deepseek,kimi \
  --api-key deepseek=sk-xxx \
  --api-key kimi=sk-yyy

# Listen on all interfaces (for Docker/LAN)
local-gateway --providers deepseek,kimi --host 0.0.0.0
```

## Configuration

### Environment Variables

| Provider | Env Variable |
|----------|-------------|
| DeepSeek | `DEEPSEEK_API_KEY` |
| KIMI | `KIMI_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Together | `TOGETHER_API_KEY` |
| Mistral | `MISTRAL_API_KEY` |
| Google Gemini | `GOOGLE_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |

### Using with any OpenAI-compatible client

```python
import openai
client = openai.OpenAI(
    base_url="http://127.0.0.1:18790/v1",
    api_key="not-needed",  # local-gateway doesn't validate the client key
)
```

## How It Works

```
                    ┌─────────────────┐
Client ──POST──→  local-gateway      │
                    │                  │
                    ├→ try DeepSeek ──→ HTTP 200 → forward response
                    │                  │
                    └→ DeepSeek fails  │
                      → try KIMI ────→ HTTP 200 → forward response
                                       │
                         all fail ────→ 502
```

For SSE streaming, the proxy connects to the upstream **before** sending HTTP 200 to the client. This means failover is transparent — the client never sees a partial response.

## Built-in Providers

See `local-gateway --list-providers` for the full list.

## Cross-Provider Model Mappings

See `local-gateway --list-models` for the current mapping table.

## Need Help Integrating?

Need help deploying LocalGateway for your team, or integrating it into your existing infrastructure?

📅 [Book a 30-min consultation](mailto:wanggui.gui@neuralbridge.cn?subject=LocalGateway%20Integration%20Support)

- **$200/hour** — Architecture review & integration guidance
- **$500/engagement** — Full deployment + configuration for your team

## Related Projects

| Project | What it does |
|---------|-------------|
| [NeuralBridge](https://github.com/Correctover/neuralbridge-sdk) | Self-healing engine for LLM APIs — 87 rules, MAPE-K loop, contract validation |
| [Correctover](https://github.com/Correctover/Correctover-) | Enterprise AI reliability SDK — full 6-dimension verification + failover |

## License

Apache 2.0

---

Built by [Correctover](https://correctover.com) — verified failover for LLM APIs.
