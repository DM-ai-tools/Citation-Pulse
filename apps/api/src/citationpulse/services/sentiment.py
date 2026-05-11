"""Snippet-level sentiment classifier.

Routed through OpenRouter using a small, cheap model (`anthropic/claude-3.5-haiku`
by default — fast and quality is fine for a single-word classification).

Caches by SHA-256 hash so repeated snippets only cost one API call.
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache

from citationpulse.core.config import get_settings
from citationpulse.services.llm_router import (
    LLMConfigError,
    LLMProviderError,
    chat_completion_sync,
    openrouter_configured,
)

_log = logging.getLogger(__name__)


@lru_cache(maxsize=2048)
def sentiment_for_snippet_cached(snippet_hash: str, snippet: str) -> str | None:
    """Return 'positive' | 'neutral' | 'negative' | None.

    Uses a cheap OpenRouter model. Returns None when:
      * `OPENROUTER_API_KEY` is not configured, or
      * the snippet is empty, or
      * the upstream call fails (we never crash callers over a sentiment label).
    """
    settings = get_settings()
    if not snippet or not openrouter_configured(settings):
        return None
    # Legacy override so old `.env`s with ANTHROPIC_SENTIMENT_MODEL still work.
    model = settings.anthropic_sentiment_model or settings.sentiment_model
    try:
        resp = chat_completion_sync(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Classify sentiment as exactly one word: positive, neutral, or negative.\n"
                        f'Snippet:\n"""{snippet[:800]}"""'
                    ),
                }
            ],
            max_tokens=8,
            temperature=0.0,
        )
    except (LLMConfigError, LLMProviderError) as exc:
        _log.debug("sentiment skip: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        _log.debug("sentiment unexpected error: %s", exc)
        return None

    t = (resp.text or "").strip().lower()
    if "positive" in t:
        return "positive"
    if "negative" in t:
        return "negative"
    return "neutral"


def snippet_hash(snippet: str | None) -> str:
    return hashlib.sha256((snippet or "").encode()).hexdigest()[:32]


def classify_snippet(snippet: str | None) -> str | None:
    h = snippet_hash(snippet)
    return sentiment_for_snippet_cached(h, snippet or "")
