"""Structured gap analysis for the dashboard Gaps page (unique copy per row)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from citationpulse.services.opportunities import (
    CITED_LOWER,
    CITED_TOP,
    COMPETITOR_ONLY,
    MISSING,
    engine_label,
    fmt_volume,
    list_opportunities_for_brand,
)
from citationpulse.services.opportunity_detail import (
    OpportunityDetailContext,
    gather_opportunity_context,
)

_STATE_PLAIN: dict[str, str] = {
    MISSING: "your brand is not cited",
    COMPETITOR_ONLY: "only competitors are cited",
    CITED_TOP: "cited near the top",
    CITED_LOWER: "cited lower in the answer",
}


@dataclass
class GapAnalysisPayload:
    opportunity_id: str
    title: str
    short_label: str
    grade: str
    heat: str
    gap_type: str
    summary: str
    detailed_explanation: str
    why_it_matters: str
    competitive_impact: str
    suggested_direction: str
    affected_engines: list[str]
    engine_breakdown: list[str]
    est_volume: int | None
    opportunity_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _snippet(text: str, max_len: int = 100) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def _short_label(ctx: OpportunityDetailContext) -> str:
    engine = engine_label(ctx.scope) if ctx.scope else None
    labels = {
        "absent_all": "Absent across AI engines",
        "competitor_dominant": "Competitor-led visibility",
        "engine_specific_gap": f"Missing on {engine}" if engine else "Engine-specific visibility gap",
        "weak_engine": f"Weak presence on {engine}" if engine else "Weak engine visibility",
        "refresh_content": f"Visibility lost on {engine}" if engine else "Citation refresh needed",
        "extend_presence": f"Extend presence on {engine}" if engine else "Partial engine coverage",
    }
    return labels.get(ctx.gap_type, f"{ctx.heat} priority gap")


def _affected_engines(ctx: OpportunityDetailContext) -> list[str]:
    out: list[str] = []
    for eng, state in ctx.engine_states.items():
        if state in (MISSING, COMPETITOR_ONLY):
            out.append(engine_label(eng))
    if not out and ctx.scope:
        out.append(engine_label(ctx.scope))
    return out


def _engine_breakdown(ctx: OpportunityDetailContext) -> list[str]:
    return [
        f"{engine_label(eng)}: {_STATE_PLAIN.get(state, state.replace('_', ' ').lower())}"
        for eng, state in ctx.engine_states.items()
    ]


def _cited_engine_count(ctx: OpportunityDetailContext) -> int:
    return sum(1 for s in ctx.engine_states.values() if s in (CITED_TOP, CITED_LOWER))


def _missing_engine_names(ctx: OpportunityDetailContext) -> list[str]:
    return [engine_label(e) for e, s in ctx.engine_states.items() if s == MISSING]


def _competitor_only_names(ctx: OpportunityDetailContext) -> list[str]:
    return [engine_label(e) for e, s in ctx.engine_states.items() if s == COMPETITOR_ONLY]


def _grade_note(grade: str) -> str:
    if grade == "A":
        return "Priority: address in the current sprint."
    if grade == "B":
        return "Priority: schedule right after HOT gaps."
    return "Priority: monitor; tackle after higher-impact gaps close."


def _detailed_explanation(ctx: OpportunityDetailContext) -> str:
    q = _snippet(ctx.prompt_text, 110)
    brand = ctx.brand_name
    n = len(ctx.engine_states)
    cited_n = _cited_engine_count(ctx)
    eng = engine_label(ctx.scope) if ctx.scope else None
    scope_state = ctx.engine_states.get(ctx.scope or "", MISSING) if ctx.scope else MISSING

    if ctx.gap_type == "absent_all":
        missing = ", ".join(_missing_engine_names(ctx)) or "all tracked engines"
        return (
            f"For “{q}”, {brand} is not cited on {missing}. "
            f"Live scans show competitors or publishers owning all {n} engine answers for this prompt."
        )
    if ctx.gap_type == "competitor_dominant":
        comp_engines = ", ".join(_competitor_only_names(ctx)) or "multiple engines"
        comp = ctx.top_competitor or "competitors"
        return (
            f"For “{q}”, {comp} (or similar rivals) are cited on {comp_engines} while {brand} never appears. "
            "The gap is demand-wide, not a single-model glitch."
        )
    if ctx.gap_type == "engine_specific_gap" and eng:
        other_cited = [
            engine_label(e)
            for e, s in ctx.engine_states.items()
            if e != ctx.scope and s in (CITED_TOP, CITED_LOWER)
        ]
        others_txt = ", ".join(other_cited) if other_cited else f"{cited_n} other engine(s)"
        return (
            f"For “{q}”, {brand} is {_STATE_PLAIN.get(scope_state, 'not cited')} on {eng} "
            f"but is present on {others_txt}. The gap is isolated to {eng} for this buyer question."
        )
    if ctx.gap_type == "weak_engine" and eng:
        return (
            f"For “{q}”, {brand} may appear on {eng} but ranks below rivals "
            f"({ _STATE_PLAIN.get(scope_state, 'weak visibility') }). "
            f"You still have presence on {cited_n} other engine(s), so the issue is strength on {eng}, not total absence."
        )
    if ctx.gap_type == "refresh_content" and eng:
        comp = ctx.top_competitor or "a competitor"
        return (
            f"For “{q}”, {brand} dropped off {eng} while {comp} now leads the citation set. "
            f"Earlier runs cited you here; the latest scan no longer does ({ctx.consecutive_gap_runs} consecutive gap run(s))."
        )
    if ctx.gap_type == "extend_presence" and eng:
        open_engines = ", ".join(_missing_engine_names(ctx)) or eng
        return (
            f"For “{q}”, {brand} has patchy coverage: still open on {open_engines} "
            f"({cited_n}/{n} engines show a brand cite). Buyers using those engines will not discover you for this intent."
        )
    return f"For “{q}”, {brand} shows uneven visibility across engines ({ctx.description})."


def _why_it_matters(ctx: OpportunityDetailContext) -> str:
    vol = f" Roughly {fmt_volume(ctx.est_volume)}/mo search demand." if ctx.est_volume else ""
    eng = engine_label(ctx.scope) if ctx.scope else None
    q = _snippet(ctx.prompt_text, 60)

    if ctx.gap_type == "absent_all":
        return (
            f"Shoppers comparing options for “{q}” never see {ctx.brand_name} in the AI summary they trust.{vol} "
            "You lose consideration before a site visit."
        )
    if ctx.gap_type == "competitor_dominant":
        return (
            f"This intent (“{q}”) currently routes trust to rivals in AI answers.{vol} "
            f"{ctx.brand_name} is excluded from the shortlist users act on."
        )
    if ctx.gap_type == "engine_specific_gap" and eng:
        return (
            f"Teams that rely on {eng} for research on “{q}” will not encounter {ctx.brand_name}.{vol} "
            "Your strong cites elsewhere do not help that audience."
        )
    if ctx.gap_type == "weak_engine" and eng:
        return (
            f"On {eng}, “{q}” answers position rivals ahead of {ctx.brand_name}.{vol} "
            "Being listed lower is often treated as “not recommended.”"
        )
    if ctx.gap_type == "refresh_content" and eng:
        return (
            f"A recent shift on {eng} for “{q}” signals {ctx.brand_name} is no longer the default answer.{vol} "
            "Returning buyers may assume a competitor replaced you."
        )
    if ctx.gap_type == "extend_presence" and eng:
        return (
            f"“{q}” still has blind spots on {eng} (and possibly other open engines).{vol} "
            f"Prospects who start on {eng} never enter your funnel."
        )
    return f"Uneven AI visibility on “{q}” caps discovery for {ctx.brand_name}.{vol}"


def _competitive_impact(ctx: OpportunityDetailContext) -> str:
    comp = ctx.top_competitor
    eng = engine_label(ctx.scope) if ctx.scope else "the open engine(s)"
    q = _snippet(ctx.prompt_text, 55)

    if ctx.gap_type == "absent_all":
        return (
            f"For “{q}”, publishers and rivals can own 100% of citations. "
            f"{f'Top domain spotted: {comp}.' if comp else 'No single rival dominates — the category itself is crowded.'}"
        )
    if ctx.gap_type == "competitor_dominant":
        rivals = ", ".join(_competitor_only_names(ctx)) or "several engines"
        return (
            f"On {rivals}, answers for “{q}” cite competitors instead of {ctx.brand_name}. "
            f"{f'{comp} is the leading cited domain in recent runs.' if comp else 'Multiple competitor domains share the cite pool.'}"
        )
    if ctx.gap_type == "engine_specific_gap":
        return (
            f"{eng} answers for “{q}” surface {comp or 'competitor or third-party'} sources while omitting {ctx.brand_name}. "
            "Share of voice on that engine goes to others for this query only."
        )
    if ctx.gap_type == "weak_engine":
        return (
            f"On {eng}, “{q}” ranks competitor citations above {ctx.brand_name}. "
            f"{f'{comp} is currently the strongest cited rival there.' if comp else 'Several rival domains outrank your pages in the cite list.'}"
        )
    if ctx.gap_type == "refresh_content":
        return (
            f"{comp or 'A competitor'} likely took the top cite on {eng} for “{q}” after your brand fell out. "
            "Users see their domain as the fresher authority."
        )
    if ctx.gap_type == "extend_presence":
        open_list = ", ".join(_missing_engine_names(ctx)) or eng
        return (
            f"Engines still open ({open_list}) send “{q}” traffic to {comp or 'other cited brands'} instead of {ctx.brand_name}. "
            "Each open engine is share you do not capture."
        )
    return f"Competitors gain discovery share on “{q}” whenever {ctx.brand_name} is missing or weak."


def _suggested_direction(ctx: OpportunityDetailContext) -> str:
    eng = engine_label(ctx.scope) if ctx.scope else "the open engine"
    q = _snippet(ctx.prompt_text, 50)
    note = _grade_note(ctx.grade)

    if ctx.gap_type == "absent_all":
        return (
            f"Create a definitive page for “{q}”, mirror structure from top-cited URLs in your category, "
            f"and pitch listicles or directories already appearing in answers. {note}"
        )
    if ctx.gap_type == "competitor_dominant":
        return (
            f"Publish a comparison for “{q}” ({ctx.brand_name} vs. named rivals), earn backlinks from sources "
            f"{ctx.top_competitor or 'competitors'} already use, and refresh pricing/trust signals. {note}"
        )
    if ctx.gap_type == "engine_specific_gap":
        return (
            f"Ship {eng}-friendly content for “{q}” (clear FAQs, schema, recent publish date) and earn 2–3 citations "
            f"on domains {eng} already trusts for this topic. {note}"
        )
    if ctx.gap_type == "weak_engine":
        return (
            f"Strengthen {eng} signals for “{q}”: update the ranking URL, add expert quotes, and secure mentions "
            f"on publications that outrank you today. {note}"
        )
    if ctx.gap_type == "refresh_content":
        return (
            f"Compare your last cited URL vs. current {eng} winners for “{q}”; refresh facts, reclaim links, "
            f"and re-index the updated page. {note}"
        )
    if ctx.gap_type == "extend_presence":
        return (
            f"Target {eng} first for “{q}” with a focused landing page plus outreach to publishers cited "
            f"in live {eng} answers. {note}"
        )
    return f"Improve on-page proof and third-party mentions for “{q}”. {note}"


def build_gap_analysis(
    ctx: OpportunityDetailContext,
    *,
    opportunity_score: float,
) -> GapAnalysisPayload:
    prompt_title = ctx.prompt_text[:512] if len(ctx.prompt_text) <= 512 else ctx.prompt_text[:509] + "…"

    return GapAnalysisPayload(
        opportunity_id=str(ctx.opportunity_id),
        title=prompt_title,
        short_label=_short_label(ctx),
        grade=ctx.grade,
        heat=ctx.heat,
        gap_type=ctx.gap_type,
        summary=ctx.description,
        detailed_explanation=_detailed_explanation(ctx),
        why_it_matters=_why_it_matters(ctx),
        competitive_impact=_competitive_impact(ctx),
        suggested_direction=_suggested_direction(ctx),
        affected_engines=_affected_engines(ctx),
        engine_breakdown=_engine_breakdown(ctx),
        est_volume=ctx.est_volume,
        opportunity_score=opportunity_score,
    )


def list_gap_analysis_for_brand(db: Session, brand_id: UUID, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = list_opportunities_for_brand(db, brand_id, status="open")[:limit]
    out: list[dict[str, Any]] = []
    for o in rows:
        ctx = gather_opportunity_context(db, o.id)
        if ctx is None:
            continue
        payload = build_gap_analysis(ctx, opportunity_score=float(o.opportunity_score))
        out.append(payload.to_dict())
    return out
