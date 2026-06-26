# Contributing to LocalGateway

Thanks for your interest! LocalGateway is an open-source project
by [Correctover](https://correctover.com), Apache 2.0 licensed.

## How to contribute

### 1. Add a new provider

Edit `src/local_gateway/providers.py` (Python) or `src/local-gateway.js` (Node.js):

```python
BUILTIN_PROVIDERS["my-provider"] = {
    "name": "my-provider",
    "base_url": "https://api.my-provider.com/v1",
    "env_key": "MY_PROVIDER_API_KEY",
    "default_model": "my-default-model",
}
```

### 2. Add model name mappings

**The most valuable contribution you can make.**

Model names are not portable across LLM providers. `deepseek-chat` on DeepSeek becomes
`moonshot-v1-128k` on KIMI. Without this mapping, auto-failover returns 404.

Add mappings to **both**:

- `src/local_gateway/providers.py` — `MODEL_MAP` dict (Python)
- `src/local-gateway.js` — `MODEL_MAP` object (Node.js)
- `models.json` — structured data file (used by tools and CI)

Mapping format:

```python
# Python (providers.py)
MODEL_MAP[("gpt-4o", "openai", "kimi")] = "moonshot-v1-128k"
```

```js
// JavaScript (local-gateway.js)
'gpt-4o|openai|kimi': 'moonshot-v1-128k',
```

```json
// models.json
{
  "model": "gpt-4o",
  "from_provider": "openai",
  "to_provider": "kimi",
  "mapped_name": "moonshot-v1-128k",
  "notes": "KIMI's most capable model"
}
```

### 3. Submit a PR

1. Fork the repo
2. Make your changes (keep both Python and JS in sync)
3. Run `node -e "require('./src/local-gateway')"` to verify JS loads
4. Run `python -c "from local_gateway.providers import MODEL_MAP; print(len(MODEL_MAP))"` to verify Python loads
5. Submit a PR with a clear description of the mapping

## Mapping quality guidelines

| Label | When to use |
|-------|------------|
| **Exact** | Same model name or documented alias (e.g. `gpt-4o` → `openai/gpt-4o`) |
| **Approximate** | No exact equivalent, but functionally similar (e.g. `claude-sonnet` → `gpt-4o`) |
| **Best effort** | Different model family, used to prevent 404 |

Mark approximate mappings in the `notes` field so users know the trade-off.

## Development

```bash
# Python
pip install -e .
local-gateway --providers deepseek,kimi

# Node.js
node src/local-gateway.js --providers deepseek,kimi
```

## Code of Conduct

Be respectful. This is a small project — every contributor matters.
