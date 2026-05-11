"""Gemini engine adapter.

Routed through OpenRouter (`google/gemini-2.0-flash-001:online` by default).
The `:online` suffix activates OpenRouter's web-search plugin to surface URL
citations consistently with the other adapters.
"""

from __future__ import annotations

import time
from typing import Any

from citationpulse.adapters.base import BaseEngineAdapter, EngineResponse, RawCitation
from citationpulse.core.config import get_settings
from citationpulse.models.domain import EngineType
from citationpulse.services.llm_router import LLMConfigError, get_router, openrouter_configured
from citationpulse.storage.r2 import upload_openrouter_response_raw


class GeminiAdapter(BaseEngineAdapter):
    def __init__(self) -> None:
        super().__init__(EngineType.GEMINI)

    async def run(self, prompt: str, locale: str, run_ctx: dict[str, Any]) -> EngineResponse:
        settings = get_settings()
        t0 = time.perf_counter()
        if not openrouter_configured(settings):
            return EngineResponse("", [], "", int((time.perf_counter() - t0) * 1000), None)

        model = settings.google_ai_model or settings.gemini_model
        try:
            resp = await get_router().chat_completion(
                model=model,
                messages=[{"role": "user", "content": f"[{locale}] {prompt}"}],
            )
        except LLMConfigError:
            return EngineResponse("", [], "", int((time.perf_counter() - t0) * 1000), None)

        key = f"raw/{run_ctx.get('run_id','unknown')}/openrouter_gemini.json"
        upload_openrouter_response_raw(key, resp.raw)
        cites = [
            RawCitation(url=c.url, snippet=c.snippet, position=c.position)
            for c in resp.citations
        ]
        return EngineResponse(
            answer_text=resp.text,
            citations=cites,
            raw_payload_ref=key,
            latency_ms=resp.latency_ms,
            cost_usd=resp.cost_usd,
        )
