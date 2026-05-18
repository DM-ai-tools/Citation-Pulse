"""Engine routing: direct keys vs OpenRouter."""

from __future__ import annotations

from citationpulse.core.config import Settings
from citationpulse.services.engine_routing import (
    build_engine_routes,
    engine_can_run,
    engine_route,
)


def test_chatgpt_prefers_openai_direct() -> None:
    s = Settings(
        openai_api_key="sk-test",
        openrouter_api_key="sk-or-test",
    )
    assert engine_route("chatgpt", s) == "openai_direct"


def test_claude_prefers_anthropic_direct() -> None:
    s = Settings(
        anthropic_api_key="sk-ant-test",
        openrouter_api_key="sk-or-test",
    )
    assert engine_route("claude", s) == "anthropic_direct"


def test_gemini_requires_openrouter() -> None:
    s = Settings(openrouter_api_key="sk-or-test")
    assert engine_route("gemini", s) == "openrouter"
    s2 = Settings()
    assert engine_route("gemini", s2) == "unconfigured"


def test_available_routes_mixed() -> None:
    s = Settings(openai_api_key="a", anthropic_api_key="b", openrouter_api_key="c")
    routes = build_engine_routes(["chatgpt", "claude", "gemini", "perplexity"], s)
    assert routes["chatgpt"] == "openai_direct"
    assert routes["claude"] == "anthropic_direct"
    assert routes["gemini"] == "openrouter"
    assert engine_can_run("perplexity", s)
