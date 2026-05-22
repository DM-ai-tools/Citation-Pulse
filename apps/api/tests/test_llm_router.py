"""Unit tests for the OpenRouter LLM router — all citation/text/model paths without live API calls."""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.core.config import Settings  # noqa: E402
from citationpulse.models.domain import EngineType, Ownership, RunStatus  # noqa: E402
from citationpulse.services import engine_routing  # noqa: E402
from citationpulse.services.llm_router import (  # noqa: E402
    LLMConfigError,
    LLMProviderError,
    LLMRouter,
    LLMResponse,
    _cost_from_usage,
    _enable_web_if_needed,
    _extract_citations,
    _extract_text,
    _normalise_openrouter_key,
    openrouter_configured,
)
from citationpulse.services.scans_flow import cell_status_for_run  # noqa: E402

# --------------------------------------------------------------------------- #
# API key normalisation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, ""),
        ("", ""),
        ("  sk-or-test  ", "sk-or-test"),
        ("\ufeff'sk-or-x'", "sk-or-x"),
        ('"quoted-key"', "quoted-key"),
        ("Bearer sk-or-bearer", "sk-or-bearer"),
        ("bearer lowercase", "lowercase"),
    ],
)
def test_normalise_openrouter_key(raw: str | None, expected: str) -> None:
    assert _normalise_openrouter_key(raw) == expected


@pytest.mark.parametrize(
    "key,configured",
    [
        ("", False),
        ("sk-live", True),
    ],
)
def test_openrouter_configured(key: str, configured: bool) -> None:
    s = Settings(openrouter_api_key=key)
    assert openrouter_configured(s) is configured


# --------------------------------------------------------------------------- #
# Web plugin (`:online`) on model slugs
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "model,expected",
    [
        ("openai/gpt-4o-mini:online", "openai/gpt-4o-mini:online"),
        ("anthropic/claude-sonnet-4:online", "anthropic/claude-sonnet-4:online"),
        ("openai/gpt-4o-mini", "openai/gpt-4o-mini:online"),
        ("anthropic/claude-sonnet-4", "anthropic/claude-sonnet-4:online"),
        ("google/gemini-2.0-flash-001", "google/gemini-2.0-flash-001:online"),
        ("perplexity/sonar", "perplexity/sonar"),
        ("openai/gpt-4o-search-preview", "openai/gpt-4o-search-preview"),
        ("perplexity/sonar-pro", "perplexity/sonar-pro"),
    ],
)
def test_enable_web_if_needed(model: str, expected: str) -> None:
    assert _enable_web_if_needed(model) == expected


# --------------------------------------------------------------------------- #
# Citation extraction (every provider payload shape)
# --------------------------------------------------------------------------- #


def test_extract_citations_anthropic_content_blocks() -> None:
    payload = {
        "content": [
            {
                "type": "text",
                "text": "Answer",
                "citations": [
                    {"url": "https://brand.example/a", "title": "A", "cited_text": "snippet"},
                ],
            }
        ]
    }
    cites = _extract_citations(payload, "Answer")
    assert len(cites) == 1
    assert cites[0].url == "https://brand.example/a"
    assert cites[0].title == "A"
    assert cites[0].snippet == "snippet"


def test_extract_citations_search_results_and_root_list() -> None:
    payload = {
        "search_results": [{"url": "https://one.test", "title": "One", "snippet": "s1"}],
        "citations": ["https://two.test", {"url": "https://three.test", "title": "Three"}],
    }
    cites = _extract_citations(payload, "")
    urls = [c.url for c in cites]
    assert urls == ["https://one.test", "https://two.test", "https://three.test"]


def test_extract_citations_openrouter_annotations() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "url": "https://ann.test",
                                "title": "Ann",
                                "content": "body",
                            },
                        },
                        {
                            "url_citation": {"uri": "https://flat.test", "snippet": "flat"},
                        },
                    ]
                }
            }
        ]
    }
    cites = _extract_citations(payload, "")
    assert {c.url for c in cites} == {"https://ann.test", "https://flat.test"}


def test_extract_citations_message_content_nested() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {
                            "citations": [
                                {"url": "https://nested.test", "title": "N", "cited_text": "x"},
                            ]
                        }
                    ]
                }
            }
        ]
    }
    cites = _extract_citations(payload, "")
    assert cites[0].url == "https://nested.test"


def test_extract_citations_regex_fallback_and_dedup() -> None:
    text = "See https://dup.test and https://dup.test/path."
    payload = {"citations": ["https://dup.test"]}
    cites = _extract_citations(payload, text)
    urls = [c.url for c in cites]
    assert urls.count("https://dup.test") == 1
    assert "https://dup.test/path." in urls or any("dup.test/path" in u for u in urls)


def test_extract_citations_empty_payload() -> None:
    assert _extract_citations({}, "") == []


# --------------------------------------------------------------------------- #
# Assistant text extraction
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"choices": [{"message": {"content": "plain string"}}]}, "plain string"),
        (
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "part1 "},
                                {"type": "text", "text": "part2"},
                            ]
                        }
                    }
                ]
            },
            "part1 part2",
        ),
        ({"choices": [{"text": "legacy"}]}, "legacy"),
        ({"choices": []}, ""),
        (
            {
                "choices": [
                    {
                        "message": {
                            "content": "main",
                            "reasoning": "think",
                            "refusal": "nope",
                        }
                    }
                ]
            },
            "main\nthink\nnope",
        ),
    ],
)
def test_extract_text(payload: dict, expected: str) -> None:
    assert _extract_text(payload) == expected


@pytest.mark.parametrize(
    "usage,expected",
    [
        ({"cost": "0.0012"}, Decimal("0.0012")),
        ({"cost": 0.5}, Decimal("0.5")),
        ({}, None),
        ({"cost": "not-a-number"}, None),
    ],
)
def test_cost_from_usage(usage: dict, expected: Decimal | None) -> None:
    assert _cost_from_usage({"usage": usage}) == expected


# --------------------------------------------------------------------------- #
# Engine routing matrix (direct vs OpenRouter vs unconfigured)
# --------------------------------------------------------------------------- #


def _isolated_settings(**overrides: object) -> Settings:
    """Settings with no keys from repo .env unless explicitly overridden."""
    base: dict[str, object] = {
        "openrouter_api_key": "",
        "openai_api_key": "",
        "anthropic_api_key": "",
        "google_ai_api_key": "",
        "perplexity_api_key": "",
        "claude_prefer_openrouter": False,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "engine,overrides,route",
    [
        ("gemini", {"openrouter_api_key": "sk"}, "openrouter"),
        ("gemini", {}, "unconfigured"),
        ("perplexity", {"openrouter_api_key": "sk"}, "openrouter"),
        ("chatgpt", {"openai_api_key": "sk-openai"}, "openai_direct"),
        ("chatgpt", {"openrouter_api_key": "sk-or"}, "openrouter"),
        ("chatgpt", {}, "unconfigured"),
        ("claude", {"anthropic_api_key": "sk-ant"}, "anthropic_direct"),
        ("claude", {"openrouter_api_key": "sk-or"}, "openrouter"),
        (
            "claude",
            {
                "anthropic_api_key": "sk-ant",
                "claude_prefer_openrouter": True,
                "openrouter_api_key": "sk-or",
            },
            "openrouter",
        ),
        ("unknown_engine", {"openrouter_api_key": "sk"}, "unconfigured"),
    ],
)
def test_engine_route_matrix(engine: str, overrides: dict, route: str) -> None:
    s = _isolated_settings(**overrides)
    assert engine_routing.engine_route(engine, s) == route
    assert engine_routing.engine_can_run(engine, s) == (route != "unconfigured")


def test_effective_model_overrides() -> None:
    s = Settings(openai_model="gpt-override", anthropic_model="claude-override")
    assert engine_routing.effective_openai_model(s) == "gpt-override"
    assert engine_routing.effective_anthropic_model(s) == "claude-override"
    s2 = Settings()
    assert engine_routing.effective_openai_model(s2) == s2.openai_direct_model
    assert engine_routing.effective_anthropic_model(s2) == s2.anthropic_direct_model


# --------------------------------------------------------------------------- #
# Scan cell status (UI matrix model)
# --------------------------------------------------------------------------- #


def _mock_run(
    *,
    status: str,
    error_message: str | None = None,
    prompt_id: str = "00000000-0000-0000-0000-000000000001",
    engine: str = EngineType.CHATGPT.value,
) -> MagicMock:
    run = MagicMock()
    run.prompt_id = prompt_id
    run.engine = engine
    run.status = status
    run.error_message = error_message
    run.id = "00000000-0000-0000-0000-000000000002"
    return run


@pytest.mark.parametrize(
    "run_status,error_msg,expected_status",
    [
        (RunStatus.QUEUED.value, None, "queued"),
        (RunStatus.RUNNING.value, None, "running"),
        (RunStatus.ERROR.value, "timeout", "error"),
        (RunStatus.ERROR.value, None, "error"),
        ("cancelled", None, "none"),
    ],
)
def test_cell_status_non_ok(
    run_status: str, error_msg: str | None, expected_status: str
) -> None:
    run = _mock_run(status=run_status, error_message=error_msg)
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    out = cell_status_for_run(db, run)
    assert out["status"] == expected_status
    assert out["citationsCount"] == 0
    if expected_status == "error" and error_msg:
        assert out.get("errorMessage") == error_msg


@pytest.mark.parametrize(
    "ownerships,expected_status,expected_position",
    [
        ([], "none", None),
        ([Ownership.NEUTRAL.value], "none", None),
        ([Ownership.COMPETITOR.value], "comp", None),
        ([Ownership.BRAND.value], "cited", 1),  # 0-based pos 0 → UI position 1
        ([Ownership.BRAND.value, Ownership.COMPETITOR.value], "cited", 1),
    ],
)
def test_cell_status_ok_ownership(
    ownerships: list[str], expected_status: str, expected_position: int | None
) -> None:
    run = _mock_run(status=RunStatus.OK.value)
    cites = []
    for i, own in enumerate(ownerships):
        c = MagicMock()
        c.ownership = own
        c.position = i
        c.url = f"https://example.com/{i}"
        c.snippet = f"snippet {i}"
        cites.append(c)
    db = MagicMock()
    db.scalars.return_value.all.return_value = cites
    out = cell_status_for_run(db, run)
    assert out["status"] == expected_status
    assert out["citationsCount"] == len(ownerships)
    if expected_position is not None:
        assert out.get("position") == expected_position


# --------------------------------------------------------------------------- #
# chat_completion HTTP behaviour (mocked)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_chat_completion_missing_key_raises() -> None:
    s = Settings(openrouter_api_key="")
    router = LLMRouter(settings=s)
    with patch("citationpulse.services.llm_router.get_settings", return_value=s):
        with pytest.raises(LLMConfigError):
            await router.chat_completion(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": "hi"}],
            )


@pytest.mark.asyncio
async def test_chat_completion_success_normalizes_response() -> None:
    payload = {
        "model": "openai/gpt-4o-mini:online",
        "choices": [
            {
                "message": {"content": "Answer with https://cite.test link."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.01},
        "citations": ["https://cite.test"],
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_resp.text = ""

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    s = Settings(openrouter_api_key="sk-test")
    router = LLMRouter(settings=s)
    with patch("citationpulse.services.llm_router._openrouter_http_client", return_value=mock_client):
        with patch("citationpulse.services.llm_router.get_settings", return_value=s):
            out = await router.chat_completion(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
            )
    assert isinstance(out, LLMResponse)
    assert "Answer" in out.text
    assert any(c.url == "https://cite.test" for c in out.citations)
    assert out.prompt_tokens == 10
    assert out.completion_tokens == 5
    assert out.cost_usd == Decimal("0.01")
    assert out.finish_reason == "stop"


@pytest.mark.asyncio
async def test_chat_completion_4xx_fails_fast() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "invalid key"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    s = Settings(openrouter_api_key="sk-bad")
    router = LLMRouter(settings=s)
    with patch("citationpulse.services.llm_router._openrouter_http_client", return_value=mock_client):
        with patch("citationpulse.services.llm_router.get_settings", return_value=s):
            with pytest.raises(LLMProviderError) as exc:
                await router.chat_completion(
                    model="openai/gpt-4o-mini",
                    messages=[{"role": "user", "content": "x"}],
                )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_chat_completion_retries_429() -> None:
    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {
        "model": "openai/gpt-4o-mini:online",
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": {},
    }
    ok.text = ""

    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.text = "slow down"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[rate_limited, ok])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    s = Settings(openrouter_api_key="sk-test", llm_max_retries=3)
    router = LLMRouter(settings=s)
    with patch("citationpulse.services.llm_router._openrouter_http_client", return_value=mock_client):
        with patch("citationpulse.services.llm_router.get_settings", return_value=s):
            out = await router.chat_completion(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": "retry"}],
            )
    assert out.text == "ok"
    assert mock_client.post.await_count == 2
