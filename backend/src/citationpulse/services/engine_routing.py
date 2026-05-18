"""Per-engine LLM routing: direct provider keys vs OpenRouter."""

from __future__ import annotations

from typing import Literal

from citationpulse.core.config import Settings, get_settings
from citationpulse.models.domain import EngineType
from citationpulse.services.llm_router import _normalise_openrouter_key, openrouter_configured

EngineRoute = Literal["openai_direct", "anthropic_direct", "openrouter", "unconfigured"]

_OPENROUTER_ONLY: frozenset[str] = frozenset(
    {EngineType.GEMINI.value, EngineType.PERPLEXITY.value}
)
_OPENAI_ENGINE: frozenset[str] = frozenset({EngineType.CHATGPT.value})
_ANTHROPIC_ENGINE: frozenset[str] = frozenset({EngineType.CLAUDE.value})


def _strip_key(raw: str | None) -> str:
    if raw is None:
        return ""
    s = str(raw).strip().lstrip("\ufeff")
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


def openai_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(_strip_key(s.openai_api_key))


def anthropic_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(_strip_key(s.anthropic_api_key))


def engine_route(engine: str, settings: Settings | None = None) -> EngineRoute:
    s = settings or get_settings()
    if engine in _OPENROUTER_ONLY:
        return "openrouter" if openrouter_configured(s) else "unconfigured"
    if engine in _OPENAI_ENGINE:
        if openai_configured(s):
            return "openai_direct"
        return "openrouter" if openrouter_configured(s) else "unconfigured"
    if engine in _ANTHROPIC_ENGINE:
        if anthropic_configured(s):
            return "anthropic_direct"
        return "openrouter" if openrouter_configured(s) else "unconfigured"
    return "unconfigured"


def engine_can_run(engine: str, settings: Settings | None = None) -> bool:
    return engine_route(engine, settings) != "unconfigured"


def build_engine_routes(engines: list[str], settings: Settings | None = None) -> dict[str, str]:
    return {e: engine_route(e, settings) for e in engines}


def route_label(route: str) -> str:
    return {
        "openai_direct": "OpenAI API (direct)",
        "anthropic_direct": "Anthropic API (direct)",
        "openrouter": "OpenRouter",
        "unconfigured": "Not configured",
    }.get(route, route)


def effective_openai_model(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    if s.openai_model:
        return s.openai_model
    return s.openai_direct_model


def effective_anthropic_model(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    if s.anthropic_model:
        return s.anthropic_model
    return s.anthropic_direct_model


def require_openai_key(settings: Settings | None = None) -> str:
    key = _strip_key((settings or get_settings()).openai_api_key)
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return key


def require_anthropic_key(settings: Settings | None = None) -> str:
    key = _strip_key((settings or get_settings()).anthropic_api_key)
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return key
