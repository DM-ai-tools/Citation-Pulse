"""Adapter smoke tests (no API keys required for empty paths)."""

import asyncio

import pytest

from citationpulse.adapters.perplexity_adapter import PerplexityAdapter


def test_perplexity_adapter_no_key():
    ad = PerplexityAdapter()
    r = asyncio.run(ad.run("test", "en-US", {"run_id": "x"}))
    assert r.citations == []


@pytest.mark.skip(reason="Playwright network smoke; run locally with --no-skip")
def test_google_aio_playwright_smoke():
    from citationpulse.adapters.google_aio import GoogleAIOAdapter

    ad = GoogleAIOAdapter()
    r = asyncio.run(ad.run("weather today", "en-US", {"run_id": "y"}))
    assert isinstance(r.answer_text, str)
