"""Expandable copy for Top Gap Opportunities (LLM when configured, else templates)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from citationpulse.core.config import Settings, get_settings
from citationpulse.models.domain import Brand, Opportunity, Prompt
from citationpulse.services.direct_llm import DirectProviderError, openai_chat_completion
from citationpulse.services.engine_routing import openai_configured
from citationpulse.services.llm_router import LLMConfigError, get_router
from citationpulse.services.opportunities import (
    CITED_LOWER,
    CITED_TOP,
    COMPETITOR_ONLY,
    MISSING,
    build_description,
    engine_label,
    engines_for_brand_opportunities,
    fmt_volume,
    heat_from_grade,
    run_to_classifier_state,
    _runs_latest_and_prev,
    _top_competitor_domain,
)

_log = logging.getLogger(__name__)

_STATE_LABEL: dict[str, str] = {
    MISSING: "brand not cited",
    COMPETITOR_ONLY: "competitors cited instead of your brand",
    CITED_TOP: "brand cited near the top",
    CITED_LOWER: "brand cited lower in the answer",
}

_GAP_TYPE_HINT: dict[str, str] = {
    "absent_all": "Your brand does not appear in AI answers for this prompt on any tracked engine.",
    "competitor_dominant": "Competitors are cited while your brand is missing on multiple engines for this query.",
    "engine_specific_gap": "You are cited on most engines but still missing on one specific engine.",
    "weak_engine": "You are cited on several engines, but competitors lead on this engine.",
    "refresh_content": "You were previously cited here; competitors now dominate and your visibility dropped.",
    "extend_presence": "Your brand is visible on some engines but still absent on at least one for this buyer question.",
}


@dataclass(frozen=True)
class OpportunityDetailContext:
    opportunity_id: UUID
    brand_id: UUID
    brand_name: str
    prompt_text: str
    gap_type: str
    scope: str | None
    grade: str
    heat: str
    description: str
    est_volume: int | None
    engine_states: dict[str, str]
    top_competitor: str | None
    consecutive_gap_runs: int


def gather_opportunity_context(db: Session, opportunity_id: UUID) -> OpportunityDetailContext | None:
    o = db.get(Opportunity, opportunity_id)
    if o is None:
        return None
    brand = db.get(Brand, o.brand_id)
    prompt = db.get(Prompt, o.prompt_id)
    if brand is None or prompt is None:
        return None

    engines = engines_for_brand_opportunities(db, o.brand_id)
    latest_runs, _prev = _runs_latest_and_prev(db, o.prompt_id, engines)
    latest_states = {e: run_to_classifier_state(db, latest_runs.get(e)) for e in engines}
    scope = (o.scope or "").strip() or None
    top_comp = _top_competitor_domain(db, latest_runs.get(scope) if scope else None)

    return OpportunityDetailContext(
        opportunity_id=o.id,
        brand_id=o.brand_id,
        brand_name=brand.name,
        prompt_text=(prompt.text or "").strip(),
        gap_type=o.gap_type,
        scope=scope,
        grade=o.grade,
        heat=heat_from_grade(o.grade),
        description=o.description,
        est_volume=o.est_volume,
        engine_states=latest_states,
        top_competitor=top_comp if top_comp != "Competitor" else None,
        consecutive_gap_runs=int(prompt.consecutive_gap_runs or 0),
    )


def _engine_breakdown_lines(ctx: OpportunityDetailContext) -> list[str]:
    lines: list[str] = []
    for eng, state in ctx.engine_states.items():
        label = engine_label(eng)
        state_txt = _STATE_LABEL.get(state, state.replace("_", " ").lower())
        lines.append(f"{label}: {state_txt}")
    return lines


def build_deterministic_detail(ctx: OpportunityDetailContext) -> str:
    """Two-sentence explanation without calling an LLM."""
    hint = _GAP_TYPE_HINT.get(ctx.gap_type, "This prompt shows uneven AI visibility for your brand.")
    scope_label = engine_label(ctx.scope) if ctx.scope else None
    if ctx.scope and scope_label:
        scope_state = ctx.engine_states.get(ctx.scope, MISSING)
        scope_line = (
            f" On {scope_label}, visibility is: {_STATE_LABEL.get(scope_state, scope_state)}."
        )
    else:
        scope_line = ""

    vol_phrase = f" (~{fmt_volume(ctx.est_volume)}/mo search demand)" if ctx.est_volume else ""
    comp = ctx.top_competitor
    comp_line = f" Leading competitor cited here: {comp}." if comp else ""

    action = {
        "A": "Treat this as a priority fix in content and PR this sprint.",
        "B": "Schedule improvements after your HOT gaps.",
        "C": "Monitor and address when higher-impact gaps are closed.",
    }.get(ctx.grade, "Review in your next visibility review.")

    return f"{hint}{scope_line}{vol_phrase}{comp_line} {action}"


def _llm_messages(ctx: OpportunityDetailContext) -> list[dict[str, str]]:
    breakdown = "; ".join(_engine_breakdown_lines(ctx)) or "No engine runs yet."
    scope_txt = engine_label(ctx.scope) if ctx.scope else "all engines"
    return [
        {
            "role": "system",
            "content": (
                "You write brief AI-search visibility gap explanations for marketing teams. "
                "Reply with exactly 2 short sentences (max 50 words total). "
                "Sentence 1: what is wrong in plain language. Sentence 2: one concrete action. "
                "No bullets, labels, or markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Brand: {ctx.brand_name}\n"
                f"Buyer prompt: {ctx.prompt_text[:400]}\n"
                f"Gap pattern: {ctx.gap_type}\n"
                f"Focus engine: {scope_txt}\n"
                f"Grade: {ctx.heat} ({ctx.grade})\n"
                f"Summary line: {ctx.description}\n"
                f"Per-engine: {breakdown}\n"
                f"Est. monthly searches: {ctx.est_volume or 'unknown'}\n"
                f"Gap open for {ctx.consecutive_gap_runs} scan(s) in a row."
            ),
        },
    ]


def _sanitize_detail(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) > 420:
        t = t[:417].rstrip() + "…"
    return t


async def generate_detail_with_llm(
    ctx: OpportunityDetailContext,
    *,
    settings: Settings | None = None,
) -> str | None:
    s = settings or get_settings()
    messages = _llm_messages(ctx)
    model_mini = "gpt-4o-mini"

    if openai_configured(s):
        try:
            resp = await openai_chat_completion(
                messages=messages,
                settings=s,
                model=model_mini,
                max_tokens=120,
            )
            text = _sanitize_detail(resp.text)
            return text or None
        except DirectProviderError as exc:
            _log.warning("opportunity_detail openai failed id=%s: %s", ctx.opportunity_id, exc)

    router = get_router()
    if not router.is_configured():
        return None
    try:
        resp = await router.chat_completion(
            model="openai/gpt-4o-mini",
            messages=messages,
            max_tokens=120,
            temperature=0.3,
        )
        text = _sanitize_detail(resp.text)
        return text or None
    except (LLMConfigError, Exception) as exc:  # noqa: BLE001
        _log.warning("opportunity_detail openrouter failed id=%s: %s", ctx.opportunity_id, exc)
        return None


async def get_opportunity_detail(
    db: Session,
    opportunity_id: UUID,
    *,
    use_llm: bool = True,
) -> tuple[str, str] | None:
    """Return (detail_text, source) where source is cached|llm|template."""
    o = db.get(Opportunity, opportunity_id)
    if o is None:
        return None

    if o.detail_expansion and o.detail_expansion.strip():
        return o.detail_expansion.strip(), "cached"

    ctx = gather_opportunity_context(db, opportunity_id)
    if ctx is None:
        return None

    detail: str | None = None
    source = "template"
    if use_llm:
        detail = await generate_detail_with_llm(ctx)
        if detail:
            source = "llm"

    if not detail:
        detail = build_deterministic_detail(ctx)
        source = "template"

    o.detail_expansion = detail
    db.commit()

    return detail, source


def rebuild_description_from_context(ctx: OpportunityDetailContext, engines: list[str]) -> str:
    """Keep template description in sync when context is rebuilt (tests / admin)."""
    return build_description(
        gap_type=ctx.gap_type,
        engines=engines,
        latest_states=ctx.engine_states,
        scope_engine=ctx.scope,
        est_volume=ctx.est_volume,
        top_competitor=ctx.top_competitor or "Competitor",
    )
