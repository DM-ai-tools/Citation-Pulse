"""Direct OpenAI + Anthropic clients (bypass OpenRouter for lower latency)."""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from citationpulse.core.config import Settings, get_settings
from citationpulse.services.engine_routing import (
    effective_anthropic_model,
    effective_openai_model,
    require_anthropic_key,
    require_openai_key,
)
from citationpulse.services.llm_router import (
    LLMCitation,
    LLMResponse,
    _URL_RE,
    _extract_citations,
    _extract_text,
)


class DirectProviderError(RuntimeError):
    """Non-OpenRouter provider failure (OpenAI / Anthropic direct)."""

    def __init__(self, provider: str, status_code: int, body: str) -> None:
        super().__init__(f"{provider} HTTP {status_code}: {body[:300]}")
        self.provider = provider
        self.status_code = status_code
        self.body = body


_log = logging.getLogger(__name__)


def _usage_cost_usd(usage: dict[str, Any] | None) -> Decimal | None:
    if not usage:
        return None
    return None


async def openai_chat_completion(
    *,
    messages: list[dict[str, Any]],
    settings: Settings | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    s = settings or get_settings()
    client = AsyncOpenAI(api_key=require_openai_key(s))
    model_name = model or effective_openai_model(s)
    t0 = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=model_name,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens or s.llm_max_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        status = getattr(exc, "status_code", None) or 502
        body = str(exc)
        raise DirectProviderError("OpenAI", int(status) if isinstance(status, int) else 502, body) from exc

    payload = resp.model_dump()
    text = _extract_text(payload)
    citations = _extract_citations(payload, text)
    usage = payload.get("usage") or {}
    return LLMResponse(
        text=text,
        citations=citations,
        model=payload.get("model") or model_name,
        raw=payload,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        cost_usd=_usage_cost_usd(usage),
        finish_reason=((payload.get("choices") or [{}])[0]).get("finish_reason"),
    )


def _as_mapping(node: Any) -> dict[str, Any] | None:
    if isinstance(node, dict):
        return node
    if hasattr(node, "model_dump"):
        try:
            dumped = node.model_dump()
            return dumped if isinstance(dumped, dict) else None
        except Exception:  # noqa: BLE001
            return None
    return None


def _extract_anthropic_message_citations(payload: dict[str, Any], answer_text: str) -> list[LLMCitation]:
    """Pull URLs from Anthropic Messages API blocks (web_search_tool_result, etc.)."""
    out: list[LLMCitation] = []
    seen: set[str] = set()

    def _push(url: str | None, title: str | None = None, snippet: str | None = None) -> None:
        if not url or url in seen:
            return
        seen.add(url)
        out.append(LLMCitation(url=url, title=title, snippet=snippet, position=len(out)))

    def _walk(node: Any) -> None:
        mapping = _as_mapping(node)
        if mapping is None:
            if isinstance(node, list):
                for item in node:
                    _walk(item)
            return
        btype = str(mapping.get("type") or "")
        if btype in ("web_search_result", "web_search_result_location") or mapping.get("url"):
            _push(
                str(mapping.get("url") or mapping.get("uri") or ""),
                mapping.get("title") if isinstance(mapping.get("title"), str) else None,
                mapping.get("snippet")
                if isinstance(mapping.get("snippet"), str)
                else mapping.get("encrypted_content")
                if isinstance(mapping.get("encrypted_content"), str)
                else None,
            )
        if btype == "text":
            for url in dict.fromkeys(_URL_RE.findall(str(mapping.get("text") or ""))):
                _push(url)
        for key in ("content", "results", "citations"):
            child = mapping.get(key)
            if child is not None:
                _walk(child)

    for block in payload.get("content") or []:
        _walk(block)

    for url in dict.fromkeys(_URL_RE.findall(answer_text or "")):
        _push(url)
    return out


async def anthropic_chat_completion(
    *,
    messages: list[dict[str, Any]],
    settings: Settings | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    web_search: bool = True,
) -> LLMResponse:
    s = settings or get_settings()
    client = AsyncAnthropic(api_key=require_anthropic_key(s))
    model_name = model or effective_anthropic_model(s)
    user_text = ""
    for m in messages:
        if m.get("role") == "user":
            user_text = str(m.get("content") or "")
            break

    kwargs: dict[str, Any] = {
        "model": model_name,
        "max_tokens": max_tokens or s.llm_max_tokens,
        "messages": [{"role": "user", "content": user_text}],
    }
    t0 = time.perf_counter()
    msg = None
    last_exc: Exception | None = None
    if web_search:
        for tool_type in ("web_search_20250305", "web_search_20260209"):
            try:
                kwargs["tools"] = [{"type": tool_type, "name": "web_search", "max_uses": 3}]
                msg = await client.messages.create(**kwargs)
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                _log.debug("anthropic web_search tool %s failed: %s", tool_type, exc)
        if msg is None and last_exc is not None:
            _log.warning("anthropic web_search unavailable, retrying without tool: %s", last_exc)
            kwargs.pop("tools", None)
    if msg is None:
        try:
            msg = await client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            status = getattr(exc, "status_code", None) or 502
            raise DirectProviderError(
                "Anthropic", int(status) if isinstance(status, int) else 502, str(exc)
            ) from exc

    payload = msg.model_dump()
    text_parts: list[str] = []
    for block in payload.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(str(block.get("text") or ""))
    text = "\n".join(p for p in text_parts if p).strip()
    citations = _extract_anthropic_message_citations(payload, text)
    if not citations and text:
        _log.warning(
            "anthropic direct: answer text (%s chars) but zero extractable citations (model=%s)",
            len(text),
            model_name,
        )
    usage = payload.get("usage") or {}
    return LLMResponse(
        text=text,
        citations=citations,
        model=payload.get("model") or model_name,
        raw=payload,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        prompt_tokens=int(usage.get("input_tokens") or 0),
        completion_tokens=int(usage.get("output_tokens") or 0),
        cost_usd=None,
        finish_reason=payload.get("stop_reason"),
    )
