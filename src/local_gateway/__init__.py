"""local-gateway — Desktop LLM gateway with multi-provider failover.

Quick start::

    # Set API keys
    export DEEPSEEK_API_KEY=sk-...
    export KIMI_API_KEY=sk-...

    # Run the gateway
    local-gateway --providers deepseek,kimi

    # Use it (point any OpenAI-compatible client at it)
    curl http://127.0.0.1:18790/v1/chat/completions \\
      -H "Content-Type: application/json" \\
      -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hello"}]}'
"""

__version__ = "0.1.1"
__all__ = ["proxy", "providers", "cli"]
