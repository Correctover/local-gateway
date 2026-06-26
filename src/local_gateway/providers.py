"""Provider configuration and cross-provider model name mapping.

Usage:
    from local_gateway.providers import load_providers, resolve_model

    providers = load_providers(["deepseek", "kimi"])
    model = resolve_model("deepseek-chat", from_provider="deepseek", to_provider="kimi")
    # → "moonshot-v1-128k"
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional

log = logging.getLogger("local-gateway")

# ── Built-in provider registry ─────────────────────────────────────────

BUILTIN_PROVIDERS = {
    "deepseek": {
        "name": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "kimi": {
        "name": "kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "env_key": "KIMI_API_KEY",
        "default_model": "moonshot-v1-128k",
    },
    "openai": {
        "name": "openai",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
    "openrouter": {
        "name": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "default_model": "openai/gpt-4o",
    },
    "anthropic": {
        "name": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
    },
    "groq": {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
    },
    "together": {
        "name": "together",
        "base_url": "https://api.together.xyz/v1",
        "env_key": "TOGETHER_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
    "mistral": {
        "name": "mistral",
        "base_url": "https://api.mistral.ai/v1",
        "env_key": "MISTRAL_API_KEY",
        "default_model": "mistral-large-latest",
    },
    "google": {
        "name": "google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_key": "GOOGLE_API_KEY",
        "default_model": "gemini-2.0-flash",
    },
}

# ── Cross-provider model name mapping ─────────────────────────────────
#
# Key insight: model names are NOT portable across providers.
# "deepseek-chat" → KIMI must become "moonshot-v1-128k".
# This table maps: (original_model_name, from_provider, to_provider) → mapped_name
#
# Expand as the community discovers more mappings.

MODEL_MAP: dict[tuple[str, str, str], str] = {
    # DeepSeek → other providers
    ("deepseek-chat", "deepseek", "kimi"): "moonshot-v1-128k",
    ("deepseek-chat", "deepseek", "openai"): "gpt-4o",
    ("deepseek-chat", "deepseek", "openrouter"): "deepseek/deepseek-chat",
    ("deepseek-chat", "deepseek", "groq"): "llama-3.3-70b-versatile",

    # OpenAI → other providers
    ("gpt-4o", "openai", "deepseek"): "deepseek-chat",
    ("gpt-4o", "openai", "kimi"): "moonshot-v1-128k",
    ("gpt-4o", "openai", "openrouter"): "openai/gpt-4o",

    # Claude → other providers (approximate)
    ("claude-sonnet-4-20250514", "anthropic", "openai"): "gpt-4o",
    ("claude-sonnet-4-20250514", "anthropic", "deepseek"): "deepseek-chat",
}


def load_providers(
    names: list[str],
    api_keys: Optional[dict[str, str]] = None,
) -> list[dict]:
    """Build provider config list from provider names.

    API keys are resolved from:
      1. ``api_keys`` dict (explicit override)
      2. Environment variable (``DEEPSEEK_API_KEY``, ``KIMI_API_KEY``, etc.)
      3. Falls back to ``<name>_API_KEY`` env var generically

    Raises ``ValueError`` if a provider's API key cannot be found.
    """
    providers = []
    for name in names:
        spec = BUILTIN_PROVIDERS.get(name)
        if spec is None:
            log.warning("Unknown provider '%s' — using generic config", name)
            spec = {
                "name": name,
                "base_url": f"https://api.{name}.com/v1",
                "env_key": f"{name.upper()}_API_KEY",
                "default_model": f"{name}-default",
            }

        api_key = None
        if api_keys and name in api_keys:
            api_key = api_keys[name]
        if not api_key:
            api_key = os.environ.get(spec["env_key"])
        if not api_key:
            api_key = os.environ.get(f"{name.upper()}_API_KEY")
        if not api_key:
            raise ValueError(
                f"API key for '{name}' not found. "
                f"Set {spec['env_key']} environment variable or pass via --api-key"
            )

        providers.append({
            "name": spec["name"],
            "base_url": spec["base_url"],
            "api_key": api_key,
            "default_model": spec["default_model"],
        })

    return providers


def resolve_model(
    original_model: str,
    from_provider: str,
    to_provider: str,
) -> str:
    """Map a model name from one provider to its equivalent on another.

    If no explicit mapping exists, returns ``original_model`` unchanged —
    the request will likely fail with a 404, which is the honest result.
    """
    key = (original_model, from_provider, to_provider)
    mapped = MODEL_MAP.get(key)
    if mapped:
        log.info("Model mapped: %s (%s) → %s (%s)", original_model, from_provider, mapped, to_provider)
        return mapped
    log.warning(
        "No model mapping for '%s' from %s → %s — passing through",
        original_model, from_provider, to_provider,
    )
    return original_model


def dump_mapping_table() -> str:
    """Return a human-readable model mapping table for display."""
    lines = ["# Cross-Provider Model Name Mapping", ""]
    seen = set()
    for (model, src, dst), mapped in sorted(MODEL_MAP.items()):
        key = (model, src)
        if key not in seen:
            if seen:
                lines.append("")
            lines.append(f"{model}  ({src})")
            seen.add(key)
        lines.append(f"  => {mapped:40s} ({dst})")
    return "\n".join(lines)
