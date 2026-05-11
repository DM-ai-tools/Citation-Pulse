"""Unified LLM gateway built on OpenRouter.

OpenRouter exposes an OpenAI-compatible Chat Completions API that proxies to
all major providers (OpenAI, Anthropic, Google, Perplexity, Meta, …) using a
single API key. This module is the ONE place in the codebase that talks to an
LLM provider. Every engine adapter, sentiment classifier, etc. routes through
`chat_completion()` below.

Why one client?
  * A single retry / timeout / cost-tracking policy.
  * One auth surface (one `OPENROUTER_API_KEY`).
  * Trivial model swapping at runtime — just pass a different `model` slug.
  * Streaming support is uniform (provider-agnostic SSE).

Citation extraction
  OpenRouter forwards provider-specific extras at the response root (e.g.
  Perplexity's `citations`, OpenRouter's web plugin `annotations`). We
  surface those plus a regex fallback over the answer text so callers get a
  consistent `LLMResponse.citations` list regardless of provider.

References:
  * https://openrouter.ai/docs/api-reference/chat-completion
  * https://openrouter.ai/docs/features/web-search
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, AsyncIterator

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from citationpulse.core.config import Settings, get_settings

_log = logging.getLogger(__name__)

# Models that already do native web search → don't add the `:online` plugin.
_NATIVE_WEB_PROVIDERS: tuple[str, ...] = ("perplexity/", "openai/gpt-4o-search-preview")


class LLMConfigError(RuntimeError):
    """Raised when the LLM router is not configured (e.g. missing API key)."""


class LLMProviderError(RuntimeError):
    """Raised when an upstream provider returned a non-recoverable error."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"OpenRouter HTTP {status_code}: {body[:300]}")
        self.status_code = status_code
        self.body = body


@dataclass
class LLMCitation:
    url: str
    title: str | None = None
    snippet: str | None = None
    position: int = 0


@dataclass
class LLMResponse:
    """Normalized chat-completion response.

    Mirrors the subset of the OpenAI/OpenRouter shape we rely on, plus a
    `citations` list extracted from provider-specific fields.
    """

    text: str
    citations: list[LLMCitation]
    model: str
    raw: dict[str, Any]
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: Decimal | None = None
    finish_reason: str | None = None


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _settings_or_default(settings: Settings | None) -> Settings:
    return settings or get_settings()


def _require_key(settings: Settings) -> str:
    if not settings.openrouter_api_key:
        raise LLMConfigError(
            "OPENROUTER_API_KEY is not set. Get one at https://openrouter.ai/keys "
            "and add it to your .env."
        )
    return settings.openrouter_api_key


def _headers(settings: Settings) -> dict[str, str]:
    h = {
        "Authorization": f"Bearer {_require_key(settings)}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_http_referer:
        h["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_app_title:
        h["X-Title"] = settings.openrouter_app_title
    return h


def _enable_web_if_needed(model: str) -> str:
    """Ensure non-search-native models pull web results via OpenRouter's plugin.

    The `:online` suffix is OpenRouter's shorthand for the web plugin and is
    safe to apply once. Native web providers (Perplexity, GPT search preview)
    stay unchanged. Without this, env overrides like ``CLAUDE_MODEL=anthropic/…``
    (no suffix) would run **without** web and often return **zero** extractable
    citations next to ChatGPT defaults that already include ``:online``.
    """
    if model.endswith(":online"):
        return model
    if any(model.startswith(prefix) for prefix in _NATIVE_WEB_PROVIDERS):
        return model
    return f"{model}:online"


# Citation extraction --------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\])>\"'`]+")


def _extract_citations(payload: dict[str, Any], answer_text: str) -> list[LLMCitation]:
    """Pull citations from every place OpenRouter / providers place them."""
    out: list[LLMCitation] = []
    seen: set[str] = set()

    def _push(url: str | None, title: str | None = None, snippet: str | None = None) -> None:
        if not url or url in seen:
            return
        seen.add(url)
        out.append(LLMCitation(url=url, title=title, snippet=snippet, position=len(out)))

    # 0) Optional plugin / search metadata at response root (varies by provider)
    for row in payload.get("search_results") or []:
        if isinstance(row, dict) and row.get("url"):
            _push(str(row["url"]), row.get("title"), row.get("snippet"))

    # 1) Perplexity / OpenRouter root-level `citations: ["url", ...]`
    for c in payload.get("citations") or []:
        if isinstance(c, str):
            _push(c)
        elif isinstance(c, dict):
            _push(c.get("url"), c.get("title"), c.get("snippet"))

    # 2) OpenRouter web plugin → `annotations` on each choice / message
    for choice in payload.get("choices") or []:
        msg = (choice or {}).get("message") or {}
        for ann in msg.get("annotations") or []:
            if not isinstance(ann, dict):
                continue
            if ann.get("type") == "url_citation" and isinstance(ann.get("url_citation"), dict):
                url_cite = ann["url_citation"]
            else:
                url_cite = ann.get("url_citation") or ann
            _push(
                url_cite.get("url") or url_cite.get("uri"),
                url_cite.get("title"),
                url_cite.get("content") or url_cite.get("snippet"),
            )
        # Anthropic-style nested `citations` on message content blocks
        for block in msg.get("content") or []:
            if isinstance(block, dict):
                for c in block.get("citations") or []:
                    if isinstance(c, dict):
                        _push(c.get("url"), c.get("title"), c.get("cited_text"))

    # 3) Regex fallback over answer text (catches plain markdown links).
    for url in dict.fromkeys(_URL_RE.findall(answer_text or "")):
        _push(url)

    return out


def _text_from_content_block(block: dict[str, Any]) -> str:
    """Normalize one message.content element (OpenAI, Anthropic, Gemini via OpenRouter)."""
    if block.get("type") == "text":
        t = block.get("text")
        return str(t) if isinstance(t, str) else ""
    t = block.get("text")
    if isinstance(t, str):
        return t
    return ""


def _message_auxiliary_text(msg: dict[str, Any]) -> str:
    """Reasoning / refusal strings some models attach beside `content` (regex URL fallback)."""
    parts: list[str] = []
    r = msg.get("reasoning")
    if isinstance(r, str) and r.strip():
        parts.append(r.strip())
    elif isinstance(r, dict):
        rt = r.get("text") or r.get("content")
        if isinstance(rt, str) and rt.strip():
            parts.append(rt.strip())
    ref = msg.get("refusal")
    if isinstance(ref, str) and ref.strip():
        parts.append(ref.strip())
    return "\n".join(parts)


def _extract_text(payload: dict[str, Any]) -> str:
    """Pull the assistant text out of an OpenAI-shape Chat Completion payload."""
    choices = payload.get("choices") or []
    if not choices:
        return ""
    choice = choices[0] or {}
    msg = choice.get("message") or {}
    content = msg.get("content")
    main = ""
    if isinstance(content, str):
        main = content
    elif isinstance(content, list):
        main = "".join(_text_from_content_block(b) for b in content if isinstance(b, dict))
    if not (main or "").strip():
        legacy = choice.get("text")
        if isinstance(legacy, str):
            main = legacy
    aux = _message_auxiliary_text(msg)
    out = (main or "").strip()
    if aux:
        out = f"{out}\n{aux}".strip() if out else aux.strip()
    return out


def _cost_from_usage(payload: dict[str, Any]) -> Decimal | None:
    """OpenRouter returns `usage.cost` (USD) on most responses."""
    usage = payload.get("usage") or {}
    cost = usage.get("cost")
    if cost is None:
        return None
    try:
        return Decimal(str(cost))
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


@dataclass
class LLMRouter:
    """Thin singleton-ish wrapper around the OpenRouter HTTP API."""

    settings: Settings = field(default_factory=get_settings)

    def is_configured(self) -> bool:
        return bool(self.settings.openrouter_api_key)

    async def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra_body: dict[str, Any] | None = None,
        timeout_s: float | None = None,
    ) -> LLMResponse:
        """Make a non-streaming chat completion request through OpenRouter.

        Retries transient 429/5xx with exponential backoff (configurable via
        `Settings.llm_max_retries`). 4xx other than 429 fail fast.
        """
        s = self.settings
        model = _enable_web_if_needed(model)
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or s.llm_max_tokens,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if extra_body:
            body.update(extra_body)

        url = f"{s.openrouter_base_url.rstrip('/')}/chat/completions"
        timeout = timeout_s or s.llm_request_timeout_s
        t0 = time.perf_counter()

        try:
            async for attempt in AsyncRetrying(
                reraise=True,
                stop=stop_after_attempt(max(1, s.llm_max_retries)),
                wait=wait_exponential(multiplier=1, min=1, max=15),
                retry=retry_if_exception_type(
                    (httpx.TimeoutException, httpx.NetworkError, _RetryableHTTPError)
                ),
            ):
                with attempt:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        resp = await client.post(url, headers=_headers(s), json=body)
                    if resp.status_code == 429 or 500 <= resp.status_code < 600:
                        raise _RetryableHTTPError(resp.status_code, resp.text)
                    if resp.status_code >= 400:
                        raise LLMProviderError(resp.status_code, resp.text)
                    payload = resp.json()
        except RetryError as exc:  # pragma: no cover — tenacity wraps last err
            raise LLMProviderError(599, str(exc)) from exc

        text = _extract_text(payload)
        citations = _extract_citations(payload, text)
        usage = payload.get("usage") or {}
        finish_reason = ((payload.get("choices") or [{}])[0]).get("finish_reason")
        if not citations and text and len(text) > 120:
            _log.debug(
                "openrouter: long answer but zero normalized citations (model=%s finish=%s)",
                payload.get("model"),
                finish_reason,
            )
        return LLMResponse(
            text=text,
            citations=citations,
            model=payload.get("model") or model,
            raw=payload,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            cost_usd=_cost_from_usage(payload),
            finish_reason=finish_reason,
        )

    async def chat_completion_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra_body: dict[str, Any] | None = None,
        timeout_s: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield raw OpenRouter SSE chunks (OpenAI-compatible).

        Each yielded value is a parsed JSON delta. Currently used by no caller,
        but exposed so future UI features (typewriter live answers) work
        without changing this module.
        """
        s = self.settings
        model = _enable_web_if_needed(model)
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or s.llm_max_tokens,
            "stream": True,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if extra_body:
            body.update(extra_body)

        url = f"{s.openrouter_base_url.rstrip('/')}/chat/completions"
        timeout = timeout_s or s.llm_request_timeout_s

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=_headers(s), json=body) as resp:
                if resp.status_code >= 400:
                    text = await resp.aread()
                    raise LLMProviderError(resp.status_code, text.decode("utf-8", errors="ignore"))
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    chunk = line.removeprefix("data: ").strip()
                    if chunk == "[DONE]":
                        return
                    try:
                        yield json.loads(chunk)
                    except json.JSONDecodeError:
                        _log.debug("openrouter: skipping malformed sse chunk: %s", chunk[:120])


class _RetryableHTTPError(Exception):
    """Internal marker — caught by tenacity to trigger retry."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"HTTP {status_code}: {body[:200]}")
        self.status_code = status_code
        self.body = body


# Module-level singleton (cheap; httpx clients are created per-call).
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Return the process-wide LLMRouter (re-reads settings on each get)."""
    global _router
    if _router is None or _router.settings is not get_settings():
        _router = LLMRouter(settings=get_settings())
    return _router


# --------------------------------------------------------------------------- #
# Sync helpers (used from Celery tasks that aren't async)
# --------------------------------------------------------------------------- #


def chat_completion_sync(**kwargs: Any) -> LLMResponse:
    """Run `chat_completion()` to completion from sync code."""
    return asyncio.run(get_router().chat_completion(**kwargs))
