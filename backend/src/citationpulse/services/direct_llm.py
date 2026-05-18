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
    LLMProviderError,
    LLMResponse,
    _URL_RE,
    _extract_citations,
    _extract_text,
)

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
        raise LLMProviderError(int(status) if isinstance(status, int) else 502, body) from exc

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


def _extract_anthropic_message_citations(payload: dict[str, Any], answer_text: str) -> list[LLMCitation]:
    """Pull URLs from Anthropic Messages API blocks (web_search_tool_result, etc.)."""
    out: list[LLMCitation] = []
    seen: set[str] = set()

    def _push(url: str | None, title: str | None = None, snippet: str | None = None) -> None:
        if not url or url in seen:
            return
        seen.add(url)
        out.append(LLMCitation(url=url, title=title, snippet=snippet, position=len(out)))

    for block in payload.get("content") or []:
        if not isinstance(block, dict):
            continue
        btype = str(block.get("type") or "")
        if btype in ("web_search_tool_result", "tool_result"):
            inner = block.get("content")
            rows = inner if isinstance(inner, list) else [inner] if isinstance(inner, dict) else []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if row.get("type") in ("web_search_result", "web_search_result_location"):
                    _push(
                        str(row.get("url") or row.get("uri") or ""),
                        row.get("title"),
                        row.get("snippet") or row.get("encrypted_content"),
                    )
                elif row.get("url"):
                    _push(str(row["url"]), row.get("title"), row.get("snippet"))
        elif btype == "text":
            for url in dict.fromkeys(_URL_RE.findall(str(block.get("text") or ""))):
                _push(url)

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
    if web_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]

    t0 = time.perf_counter()
    try:
        msg = await client.messages.create(**kwargs)
    except Exception as exc:  # noqa: BLE001
        if web_search:
            _log.debug("anthropic web_search failed, retrying without tool: %s", exc)
            kwargs.pop("tools", None)
            try:
                msg = await client.messages.create(**kwargs)
            except Exception as exc2:  # noqa: BLE001
                status = getattr(exc2, "status_code", None) or 502
                raise LLMProviderError(int(status) if isinstance(status, int) else 502, str(exc2)) from exc2
        else:
            status = getattr(exc, "status_code", None) or 502
            raise LLMProviderError(int(status) if isinstance(status, int) else 502, str(exc)) from exc

    payload = msg.model_dump()
    text_parts: list[str] = []
    for block in payload.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(str(block.get("text") or ""))
    text = "\n".join(p for p in text_parts if p).strip()
    citations = _extract_anthropic_message_citations(payload, text)
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
