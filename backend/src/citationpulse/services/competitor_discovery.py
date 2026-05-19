"""Australian-market competitor discovery via OpenRouter (web-grounded JSON)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from citationpulse.core.config import Settings, get_settings
from citationpulse.prompts.competitor_discovery import build_competitor_discovery_messages
from citationpulse.schemas.competitors import (
    CompetitorAnalyzeRequest,
    CompetitorDiscoveryResult,
)
from citationpulse.services.engine_routing import openai_configured
from citationpulse.services.llm_router import (
    LLMConfigError,
    LLMProviderError,
    chat_completion_sync,
    openrouter_configured,
)
from citationpulse.services.competitor_discovery_limits import (
    ONE_LEVEL_ABOVE_COUNT,
    SAME_LEVEL_COUNT,
)
from citationpulse.services.normalization import registrable_domain

_log = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


class CompetitorDiscoveryError(RuntimeError):
    """User-visible failure (config, provider, or invalid model output)."""


def _strip_json_payload(text: str) -> str:
    """Extract a JSON object from model text (handles optional markdown fences)."""
    raw = (text or "").strip()
    if not raw:
        raise CompetitorDiscoveryError("Model returned empty response")
    raw = _JSON_FENCE_RE.sub("", raw).strip()
    if raw.startswith("{"):
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    raise CompetitorDiscoveryError("Model response did not contain a JSON object")


def _domain_key(domain: str) -> str:
    raw = (domain or "").strip()
    if not raw:
        return ""
    url = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
    return registrable_domain(url)


def _filter_excluded(
    payload: dict[str, Any],
    excluded: set[str],
) -> dict[str, Any]:
    """Remove excluded registrable domains from competitor lists."""
    if not excluded:
        return payload

    def keep_row(row: dict[str, Any]) -> bool:
        dom = _domain_key(str(row.get("domain") or ""))
        return dom not in excluded

    out = dict(payload)
    out["same_level_competitors"] = [
        r for r in (payload.get("same_level_competitors") or []) if isinstance(r, dict) and keep_row(r)
    ]
    out["one_level_above_competitors"] = [
        r
        for r in (payload.get("one_level_above_competitors") or [])
        if isinstance(r, dict) and keep_row(r)
    ]
    target = out.get("target_company")
    if isinstance(target, dict):
        td = _domain_key(str(target.get("domain") or ""))
        if td in excluded:
            raise CompetitorDiscoveryError("Target domain cannot be in excluded_competitors")
    return out


def _validate_counts(result: CompetitorDiscoveryResult) -> None:
    n_same = len(result.same_level_competitors)
    n_above = len(result.one_level_above_competitors)
    if n_same != SAME_LEVEL_COUNT or n_above != ONE_LEVEL_ABOVE_COUNT:
        raise CompetitorDiscoveryError(
            f"Expected {SAME_LEVEL_COUNT} same-level and {ONE_LEVEL_ABOVE_COUNT} one-level-above "
            f"competitors; got {n_same} and {n_above}. Retry or adjust exclusions."
        )


def analyze_competitors(
    body: CompetitorAnalyzeRequest,
    *,
    settings: Settings | None = None,
) -> CompetitorDiscoveryResult:
    """Run competitor discovery for ``body.target_website``; returns validated JSON shape."""
    s = settings or get_settings()
    if not openrouter_configured(s) and not openai_configured(s):
        raise CompetitorDiscoveryError(
            "Set OPENROUTER_API_KEY or OPENAI_API_KEY — competitor discovery needs a web-capable model."
        )

    target_domain = registrable_domain(body.target_website)
    if not target_domain:
        raise CompetitorDiscoveryError("Could not parse domain from target_website")

    excluded = set(body.excluded_competitors)
    if target_domain in excluded:
        raise CompetitorDiscoveryError("Target domain cannot appear in excluded_competitors")

    messages = build_competitor_discovery_messages(
        target_website=body.target_website,
        competitor_type=body.competitor_type,
        service=body.service,
        niche=body.niche,
        location=body.location,
        excluded_competitors=list(excluded),
        market=body.market,
    )

    max_tokens = s.competitor_discovery_max_tokens

    try:
        if openrouter_configured(s):
            model = s.competitor_discovery_model or s.chatgpt_model
            resp = chat_completion_sync(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
            )
        else:
            import asyncio

            from citationpulse.services.direct_llm import openai_chat_completion
            from citationpulse.services.engine_routing import effective_openai_model

            resp = asyncio.run(
                openai_chat_completion(
                    messages=messages,
                    settings=s,
                    model=effective_openai_model(s),
                    max_tokens=max_tokens,
                )
            )
    except LLMConfigError as exc:
        raise CompetitorDiscoveryError(str(exc)) from exc
    except LLMProviderError as exc:
        raise CompetitorDiscoveryError(f"LLM provider error: {exc}") from exc

    try:
        raw_json = _strip_json_payload(resp.text)
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        _log.warning("competitor_discovery: invalid JSON from model: %s", resp.text[:500])
        raise CompetitorDiscoveryError("Model returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise CompetitorDiscoveryError("Model JSON must be an object")

    data = _filter_excluded(data, excluded)

    try:
        result = CompetitorDiscoveryResult.model_validate(data)
    except ValidationError as exc:
        _log.warning("competitor_discovery: schema validation failed: %s", exc)
        raise CompetitorDiscoveryError(f"Model JSON did not match schema: {exc}") from exc

    _validate_counts(result)
    return result
