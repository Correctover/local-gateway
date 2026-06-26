---
title: "I Built a Desktop AI Gateway in 73 Lines of Python — Here's Why You Need One"
description: "Every desktop AI tool (Cursor, Claude Desktop, Windsurf) lets you configure one API endpoint. When that provider goes down, your tool stops working. Here's a lightweight fix."
published: false
tags: python, llm, opensource, tutorial, ai
---

Every desktop AI tool I've used — Cursor, Claude Desktop, Windsurf, Continue — has the same limitation: **one API endpoint, one provider**. If that provider goes down, your tool stops.

This isn't a theoretical problem. In the past three months, I've seen DeepSeek go down twice, OpenAI have multi-hour outages, and various providers return 5xx errors during peak hours.

The standard advice is "use OpenRouter" or "deploy LiteLLM." But:
- **OpenRouter** means your API traffic goes through a third party
- **LiteLLM** requires Docker (200MB+), which is overkill for a desktop tool
- **Manual proxy** requires DevOps skills most desktop users don't have

So I built a 73-line solution. Here's the journey.

---

## The Problem: Model Names Are Not Portable

My setup: DeepSeek as primary, KIMI as fallback. Simple, right?

```python
# First attempt: just change the base URL
deepseek_url = "https://api.deepseek.com/v1/chat/completions"
kimi_url = "https://api.moonshot.cn/v1/chat/completions"
```

Nope. DeepSeek's model `deepseek-chat` doesn't exist on KIMI. KIMI calls its equivalent `moonshot-v1-128k`. The request returns 404.

This is the **model name mapping problem** — and it affects every multi-provider setup. GPT-4o on OpenAI becomes `openai/gpt-4o` on OpenRouter. Claude Sonnet doesn't exist on Groq. Every provider has its own naming scheme, and failover tools that ignore this will silently break.

## The Solution: Sequential Failover With Model Mapping

The architecture is dead simple:

```
Client → POST /v1/chat/completions → local-gateway
  ├── try DeepSeek → success → forward response
  └── DeepSeek fails → map model name → try KIMI → forward
```

Critical invariant: **connect to the upstream before sending HTTP 200 to the client**. If the first provider fails, try the next transparently. The client never sees a partial response.

```python
# Pure urllib, zero dependencies
for provider in providers:
    try:
        upstream = urllib.request.urlopen(
            urllib.request.Request(url, data=data, headers=headers)
        )
        # Connected! Now send 200 to client
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        # Forward SSE chunks
        while True:
            chunk = upstream.read(4096)
            if not chunk: break
            self.wfile.write(chunk)
        return
    except HTTPError:
        continue  # try next provider
# All failed → 502
```

That's the core. 73 lines total.

## Why This Matters for Desktop AI Users

Desktop AI tools are becoming the standard way developers interact with LLMs. Cursor alone has millions of users. But these tools have a single-provider dependency that creates three risks:

1. **Availability**: Your provider goes down → your tool stops working
2. **Rate limits**: One account, one set of rate limits
3. **Cost optimization**: No way to route cheap vs expensive models

A local gateway solves all three. And because it runs on `127.0.0.1` with zero external dependencies, there's no data leakage, no additional latency, no Docker overhead.

## The Result

I packaged this into a pip-installable tool:

```bash
pip install local-gateway
export DEEPSEEK_API_KEY=sk-...
export KIMI_API_KEY=sk-...
local-gateway --providers deepseek,kimi
```

Then point any OpenAI-compatible client at `http://127.0.0.1:18790/v1`:

```python
import openai
client = openai.OpenAI(
    base_url="http://127.0.0.1:18790/v1",
    api_key="not-needed",
)
```

The Node.js version is also available (`npm install local-gateway`) for Electron apps and VS Code extensions.

## What's Next

- **Model mapping contributions**: If you know the equivalent model names between providers, submit a PR. The mapping table is in `models.json`.
- **Pro version**: Dashboard, usage analytics, per-provider cost tracking
- **Correctover integration**: Verified failover — not just switching providers, but validating the response is correct

## Try It

```bash
pip install local-gateway
local-gateway --providers deepseek,kimi
# Open http://127.0.0.1:18790/health
```

Or contribute model mappings at [github.com/correctover/local-gateway](https://github.com/correctover/local-gateway).

---

*Built by [Correctover](https://correctover.com) — verified failover for LLM APIs.*
