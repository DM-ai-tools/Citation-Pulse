"""Claude engine adapter — direct Anthropic API when configured, else OpenRouter."""

from __future__ import annotations

import time
from typing import Any

from citationpulse.adapters.base import BaseEngineAdapter, EngineResponse, RawCitation
from citationpulse.core.config import get_settings
from citationpulse.models.domain import EngineType
from citationpulse.services.direct_llm import anthropic_chat_completion
from citationpulse.services.engine_routing import engine_route
from citationpulse.services.llm_router import LLMConfigError, get_router, openrouter_configured
from citationpulse.storage.r2 import upload_openrouter_response_raw


class AnthropicClaudeAdapter(BaseEngineAdapter):
    def __init__(self) -> None:
        super().__init__(EngineType.CLAUDE)

    async def run(self, prompt: str, locale: str, run_ctx: dict[str, Any]) -> EngineResponse:
        settings = get_settings()
        t0 = time.perf_counter()
        route = engine_route(EngineType.CLAUDE.value, settings)
        if route == "unconfigured":
            return EngineResponse("", [], "", int((time.perf_counter() - t0) * 1000), None)

        messages = [{"role": "user", "content": f"[{locale}] {prompt}"}]
        try:
            if route == "anthropic_direct":
                resp = await anthropic_chat_completion(messages=messages, settings=settings)
                key = f"raw/{run_ctx.get('run_id', 'unknown')}/anthropic_claude.json"
            else:
                if not openrouter_configured(settings):
                    return EngineResponse("", [], "", int((time.perf_counter() - t0) * 1000), None)
                model = settings.anthropic_model or settings.claude_model
                resp = await get_router().chat_completion(model=model, messages=messages)
                key = f"raw/{run_ctx.get('run_id', 'unknown')}/openrouter_claude.json"
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
