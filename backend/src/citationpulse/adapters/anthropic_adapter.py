"""Claude engine adapter — direct Anthropic API when configured, else OpenRouter."""

from __future__ import annotations

import logging
import time
from typing import Any

from citationpulse.adapters.base import BaseEngineAdapter, EngineResponse, RawCitation
from citationpulse.core.config import get_settings
from citationpulse.models.domain import EngineType
from citationpulse.services.direct_llm import anthropic_chat_completion
from citationpulse.services.engine_routing import engine_route
from citationpulse.services.llm_router import (
    LLMConfigError,
    LLMProviderError,
    get_router,
    openrouter_configured,
)
from citationpulse.storage.r2 import upload_openrouter_response_raw

_log = logging.getLogger(__name__)


class AnthropicClaudeAdapter(BaseEngineAdapter):
    def __init__(self) -> None:
        super().__init__(EngineType.CLAUDE)

    async def _openrouter_claude(
        self,
        *,
        messages: list[dict[str, Any]],
        settings: Any,
        run_ctx: dict[str, Any],
    ):
        model = settings.anthropic_model or settings.claude_model
        resp = await get_router().chat_completion(model=model, messages=messages)
        key = f"raw/{run_ctx.get('run_id', 'unknown')}/openrouter_claude.json"
        return resp, key

    async def run(self, prompt: str, locale: str, run_ctx: dict[str, Any]) -> EngineResponse:
        settings = get_settings()
        t0 = time.perf_counter()
        route = engine_route(EngineType.CLAUDE.value, settings)
        if route == "unconfigured":
            raise LLMConfigError(
                "Claude is not configured. Set ANTHROPIC_API_KEY and/or OPENROUTER_API_KEY on the API service."
            )

        messages = [{"role": "user", "content": f"[{locale}] {prompt}"}]
        resp = None
        key = ""

        try:
            if route == "anthropic_direct":
                try:
                    resp = await anthropic_chat_completion(messages=messages, settings=settings)
                    key = f"raw/{run_ctx.get('run_id', 'unknown')}/anthropic_claude.json"
                except LLMProviderError as exc:
                    _log.warning("anthropic direct failed run_id=%s: %s", run_ctx.get("run_id"), exc)
                    if not openrouter_configured(settings):
                        raise
                if resp is not None and not resp.citations and not (resp.text or "").strip():
                    _log.warning(
                        "anthropic direct returned empty run_id=%s; trying OpenRouter",
                        run_ctx.get("run_id"),
                    )
                    resp = None

            if resp is None:
                if not openrouter_configured(settings):
                    raise LLMConfigError(
                        "Anthropic direct returned no data and OPENROUTER_API_KEY is not set."
                    )
                resp, key = await self._openrouter_claude(
                    messages=messages, settings=settings, run_ctx=run_ctx
                )
        except LLMConfigError:
            raise

        upload_openrouter_response_raw(key, resp.raw)
        cites = [RawCitation(url=c.url, snippet=c.snippet, position=c.position) for c in resp.citations]
        return EngineResponse(
            answer_text=resp.text,
            citations=cites,
            raw_payload_ref=key,
            latency_ms=resp.latency_ms,
            cost_usd=resp.cost_usd,
        )
