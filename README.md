# LocalGateway

**Desktop LLM gateway with multi-provider failover and automatic model name mapping. Zero dependencies.**

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

**That's it. No Redis. No PostgreSQL. No Docker. No server to deploy.**

## Why?

Every desktop AI tool (Cursor, Claude Desktop, Windsurf, Continue.dev) lets you configure **one** API endpoint. If that provider goes down, your tool stops working.

LocalGateway is a lightweight proxy that sits between your desktop tools and LLM providers. It tries providers in sequence — if the first one fails, it **automatically falls back** to the next.

## Why not LiteLLM / LLM Gateway / Portkey?

| | LocalGateway | LiteLLM | LLM Gateway | Cloudflare AI Gateway |
|---|---|---|---|---|
| **Setup time** | 30 seconds | 30+ minutes | Docker/VM | Account + DNS |
| **Dependencies** | Zero | Redis + PostgreSQL | PostgreSQL + Redis | Cloudflare account |
| **Runs on** | Your laptop | Server | Server | Cloud |
| **Data leaves your machine?** | ❌ Never | Depends | Yes (proxy) | Yes (Cloudflare) |
| **Model name mapping** | ✅ Built-in | ❌ Manual | ❌ Manual | ❌ No |
| **Use with Cursor/Claude Desktop** | ✅ Just set base_url | Needs server setup | Needs server setup | Needs DNS config |

**LocalGateway is the only gateway designed for your desktop, not your server.** It runs locally, your API keys never leave your machine, and it works with any OpenAI-compatible client in one line of config.

## The Model Name Problem

Model names are not portable across providers:

| Your Request | DeepSeek | KIMI | OpenAI |
|-------------|----------|------|--------|
| `deepseek-chat` | ✅ works | ❌ 404 | ❌ unknown |
| `gpt-4o` | ❌ doesn't exist | ❌ doesn't exist | ✅ works |
| `moonshot-v1-128k` | ❌ doesn't exist | ✅ works | ❌ unknown |

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

## Quick Start with Cursor

```bash
pip install local-gateway
export DEEPSEEK_API_KEY=sk-...
export KIMI_API_KEY=sk-...
local-gateway --providers deepseek,kimi
```

Then in Cursor Settings → Models:
- Base URL: `http://localhost:18790/v1`
- API Key: `any` (LocalGateway doesn't validate)
- Model: `deepseek-chat`

If DeepSeek goes down, LocalGateway automatically switches to KIMI. No interruption.

## Supported Providers

| Provider | Env Variable | Notes |
|----------|-------------|-------|
| DeepSeek | `DEEPSEEK_API_KEY` | DeepSeek-V3, DeepSeek-R1 |
| KIMI | `KIMI_API_KEY` | Moonshot AI |
| OpenAI | `OPENAI_API_KEY` | GPT-4o, o1, etc. |
| Anthropic | `ANTHROPIC_API_KEY` | Claude 3.5, Claude 4 |
| Groq | `GROQ_API_KEY` | Llama, Mixtral |
| Together | `TOGETHER_API_KEY` | Open-source models |
| Mistral | `MISTRAL_API_KEY` | Mistral, Codestral |
| Google Gemini | `GOOGLE_API_KEY` | Gemini 2.0 |
| OpenRouter | `OPENROUTER_API_KEY` | 200+ models |

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

## Cross-Provider Model Mappings

See `local-gateway --list-models` for the current mapping table.

## Advanced Usage

### With Claude Desktop

Edit your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "local-gateway": {
      "command": "local-gateway",
      "args": ["--providers", "anthropic,openai"]
    }
  }
}
```

### As a Python SDK

```python
import openai
client = openai.OpenAI(
    base_url="http://127.0.0.1:18790/v1",
    api_key="not-needed",
)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Related Projects

| Project | What it does |
|---------|-------------|
| [NeuralBridge](https://github.com/Correctover/neuralbridge-sdk) | Self-healing engine for LLM APIs — 87 rules, MAPE-K loop, contract validation |
| [Correctover](https://correctover.com) | Enterprise AI reliability infrastructure — 6-dimension contract verification + auto-failover |

## License

Proprietary Commercial License

---

Built by [Correctover](https://correctover.com) — because failover switches, but verification confirms.
