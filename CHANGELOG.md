# Changelog

## 0.1.1 (2026-06-25)

- Fix: GBK terminal compatibility for model mapping display
- ASCII-only output in CLI

## 0.1.0 (2026-06-25)

- Initial release
- Multi-provider sequential failover (DeepSeek, KIMI, OpenAI, Anthropic, Groq, Together, Mistral, Google, OpenRouter)
- Cross-provider model name mapping (deepseek-chat → moonshot-v1-128k, etc.)
- SSE streaming passthrough (failover before headers sent)
- CLI with `local-gateway` command
- API keys via environment variables or `--api-key` flag
- Health check endpoint (`GET /health`)
- Model listing endpoint (`GET /v1/models`)
- Zero dependencies — pure Python stdlib
