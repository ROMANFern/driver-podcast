"""Multi-provider LLM client.

Providers are OpenAI-compatible endpoints listed in settings.yaml under
`llm.providers`, tried in order. This lets the pipeline run on a free model
(e.g. OpenRouter's owl-alpha) and fall back automatically to the Gemini API
free tier when the primary is unavailable. A provider is skipped if its API
key env var is unset.
"""

import os

from openai import OpenAI

from .common import get_logger, load_settings

log = get_logger("llm")


def chat(messages: list[dict], max_tokens: int = 16000) -> str:
    providers = load_settings()["llm"]["providers"]
    last_error: Exception | None = None

    for p in providers:
        api_key = os.environ.get(p["api_key_env"])
        if not api_key:
            log.info("Provider %s skipped (%s not set)", p["name"], p["api_key_env"])
            continue
        try:
            client = OpenAI(base_url=p["base_url"], api_key=api_key)
            response = client.chat.completions.create(
                model=p["model"],
                max_tokens=max_tokens,
                messages=messages,
                timeout=600,  # free/stealth models can be slow (~12 tok/s)
            )
            text = response.choices[0].message.content
            if not text or not text.strip():
                raise ValueError("empty completion")
            log.info("Completion from %s (%s)", p["name"], p["model"])
            return text
        except Exception as e:  # noqa: BLE001 - any provider failure -> next one
            log.warning("Provider %s failed: %s — trying next", p["name"], e)
            last_error = e

    raise RuntimeError(f"All LLM providers failed (last error: {last_error})")
