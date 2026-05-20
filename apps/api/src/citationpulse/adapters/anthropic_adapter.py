"""Claude engine adapter — direct Anthropic API when configured, else OpenRouter."""

from __future__ import annotations

import logging
import time
from typing import Any

from citationpulse.adapters.base import BaseEngineAdapter, EngineResponse, RawCitation
from citationpulse.core.config import get_settings
from citationpulse.models.domain import EngineType
from citationpulse.services.direct_llm import DirectProviderError, anthropic_chat_completion
from citationpulse.services.engine_routing import engine_route
from citationpulse.services.llm_router import LLMConfigError, get_router, openrouter_configured
from citationpulse.storage.r2 import upload_openrouter_response_raw

_log = logging.getLogger(__name__)


def _anthropic_billing_or_auth_failure(exc: DirectProviderError) -> bool:
    body = (exc.body or "").lower()
    if exc.status_code in (401, 402, 403):
        return True
    return any(
        token in body
        for token in ("credit balance", "too low", "billing", "insufficient", "payment", "quota")
    )


class AnthropicClaudeAdapter(BaseEngineAdapter):
    def __init__(self) -> None:
        super().__init__(EngineType.CLAUDE)

    async def _openrouter_claude(
        self,
        *,
        messages: list[dict[str, str]],
        settings: Any,
        run_ctx: dict[str, Any],
    ) -> tuple[Any, str]:
        if not openrouter_configured(settings):
            raise LLMConfigError("OPENROUTER_API_KEY is not set — cannot run Claude via OpenRouter")
        model = settings.anthropic_model or settings.claude_model
        resp = await get_router().chat_completion(model=model, messages=messages)
        key = f"raw/{run_ctx.get('run_id', 'unknown')}/openrouter_claude.json"
        return resp, key

    async def run(self, prompt: str, locale: str, run_ctx: dict[str, Any]) -> EngineResponse:
        settings = get_settings()
        t0 = time.perf_counter()
        route = engine_route(EngineType.CLAUDE.value, settings)
        if route == "unconfigured":
            return EngineResponse("", [], "", int((time.perf_counter() - t0) * 1000), None)

        messages = [{"role": "user", "content": f"[{locale}] {prompt}"}]
        try:
            if route == "anthropic_direct":
                try:
                    resp = await anthropic_chat_completion(messages=messages, settings=settings)
                    key = f"raw/{run_ctx.get('run_id', 'unknown')}/anthropic_claude.json"
                except DirectProviderError as exc:
                    if openrouter_configured(settings) and _anthropic_billing_or_auth_failure(exc):
                        _log.warning(
                            "Anthropic direct failed for Claude (%s); falling back to OpenRouter",
                            (exc.body or "")[:160],
                        )
                        resp, key = await self._openrouter_claude(
                            messages=messages, settings=settings, run_ctx=run_ctx
                        )
                    else:
                        raise
            else:
                resp, key = await self._openrouter_claude(
                    messages=messages, settings=settings, run_ctx=run_ctx
                )
        except LLMConfigError:
            return EngineResponse("", [], "", int((time.perf_counter() - t0) * 1000), None)

        upload_openrouter_response_raw(key, resp.raw)
        cites = [RawCitation(url=c.url, snippet=c.snippet, position=c.position) for c in resp.citations]
        return EngineResponse(
            answer_text=resp.text,
            citations=cites,
            raw_payload_ref=key,
            latency_ms=resp.latency_ms,
            cost_usd=resp.cost_usd,
        )
