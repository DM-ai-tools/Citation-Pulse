from __future__ import annotations

import json
import re
import time
from decimal import Decimal
from typing import Any

from citationpulse.adapters.base import BaseEngineAdapter, EngineResponse, RawCitation
from citationpulse.core.config import get_settings
from citationpulse.models.domain import EngineType
from citationpulse.storage.r2 import upload_raw_payload


class GoogleAIOAdapter(BaseEngineAdapter):
    """Best-effort Google SERP capture (AI Overview markup varies by region)."""

    def __init__(self) -> None:
        super().__init__(EngineType.GOOGLE_AIO)

    async def run(self, prompt: str, locale: str, run_ctx: dict[str, Any]) -> EngineResponse:
        settings = get_settings()
        t0 = time.perf_counter()
        try:
            from playwright.async_api import async_playwright
        except Exception:
            return EngineResponse("", [], "", int((time.perf_counter() - t0) * 1000), None)

        q = f"{prompt}"
        url = f"https://www.google.com/search?q={q}&hl={locale.split('-')[0] if '-' in locale else 'en'}"
        cites: list[RawCitation] = []
        html = ""
        async with async_playwright() as p:
            launch_kwargs: dict[str, Any] = {"headless": True}
            if settings.playwright_proxy_server:
                launch_kwargs["proxy"] = {"server": settings.playwright_proxy_server}
            browser = await p.chromium.launch(**launch_kwargs)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                html = await page.content()
            finally:
                await browser.close()
        key = f"raw/{run_ctx.get('run_id','unknown')}/google_aio.html"
        upload_raw_payload(key, html.encode(), "text/html")
        for i, u in enumerate(
            list(dict.fromkeys(re.findall(r"https?://[^\s\"'<>]+", html)))[:50]
        ):
            if "google.com" in u:
                continue
            cites.append(RawCitation(url=u, position=i))
        ms = int((time.perf_counter() - t0) * 1000)
        return EngineResponse(answer_text=html[:2000], citations=cites[:20], raw_payload_ref=key, latency_ms=ms, cost_usd=Decimal("0.01"))
