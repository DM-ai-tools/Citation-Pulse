"""Top Gap Opportunities: classify prompt×engine matrix, score, persist (nightly job)."""

from __future__ import annotations

import logging
import math
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from citationpulse.models.domain import (
    Brand,
    Citation,
    EngineRun,
    EngineType,
    Opportunity,
    Ownership,
    Prompt,
    PromptMetrics,
    RunStatus,
    default_engines,
)

_log = logging.getLogger(__name__)

# Classifier states (dev doc naming)
MISSING = "MISSING"
COMPETITOR_ONLY = "COMPETITOR_ONLY"
CITED_TOP = "CITED_TOP"
CITED_LOWER = "CITED_LOWER"


def _scope_key(engine: str | None) -> str:
    return (engine or "").strip()


def engine_label(engine: str) -> str:
    """Display names for engines in opportunity copy (default product = four LLM engines)."""
    return {
        "chatgpt": "ChatGPT",
        "claude": "Claude",
        "gemini": "Gemini",
        "perplexity": "Perplexity",
        # Legacy rows only — Google AIO is not part of required product scans.
        "google_aio": "AI Overviews",
    }.get(engine, engine.replace("_", " ").title())


def fmt_volume(v: int | None) -> str:
    if not v:
        return "low"
    if v >= 1000:
        s = f"{v / 1000:.1f}k"
        return s.rstrip("0").rstrip(".").rstrip("0").rstrip(".") if "." in s else s
    return str(int(v))


def run_to_classifier_state(db: Session, run: EngineRun | None) -> str:
    """Map latest EngineRun to MISSING | COMPETITOR_ONLY | CITED_TOP | CITED_LOWER."""
    if run is None:
        return MISSING
    if run.status in (RunStatus.QUEUED.value, RunStatus.RUNNING.value):
        return MISSING
    if run.status == RunStatus.ERROR.value or run.status != RunStatus.OK.value:
        return MISSING
    cites = list(db.scalars(select(Citation).where(Citation.engine_run_id == run.id)).all())
    if not cites:
        return MISSING
    brand_cites = [c for c in cites if c.ownership == Ownership.BRAND.value]
    comp_cites = [c for c in cites if c.ownership == Ownership.COMPETITOR.value]
    if brand_cites:
        positions = [c.position for c in brand_cites if c.position is not None]
        pos = min(positions) if positions else 999
        return CITED_TOP if pos <= 2 else CITED_LOWER
    if comp_cites:
        return COMPETITOR_ONLY
    return MISSING


def _runs_latest_and_prev(
    db: Session,
    prompt_id: UUID,
    engines: list[str],
    days: int = 120,
) -> tuple[dict[str, EngineRun | None], dict[str, EngineRun | None]]:
    """Per engine: most recent run and second-most recent (for refresh_content)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(EngineRun)
        .where(EngineRun.prompt_id == prompt_id, EngineRun.created_at >= since)
        .order_by(EngineRun.created_at.desc())
    )
    runs = list(db.scalars(stmt).all())
    by_eng: dict[str, list[EngineRun]] = defaultdict(list)
    for r in runs:
        eng = r.engine.value if isinstance(r.engine, EngineType) else str(r.engine)
        by_eng[eng].append(r)
    latest: dict[str, EngineRun | None] = {}
    prev: dict[str, EngineRun | None] = {}
    for e in engines:
        lst = by_eng.get(e, [])
        latest[e] = lst[0] if lst else None
        prev[e] = lst[1] if len(lst) > 1 else None
    return latest, prev


def classify_gap(
    latest: dict[str, str],
    prev: dict[str, str],
    engines: list[str],
) -> tuple[str, str | None] | None:
    """Return (gap_type, scope_engine_or_none) or None. First matching rule wins."""
    states = [latest.get(e, MISSING) for e in engines]
    missing = [e for e in engines if latest.get(e, MISSING) == MISSING]
    cited = [e for e in engines if latest.get(e, MISSING) in (CITED_TOP, CITED_LOWER)]
    comp = [e for e in engines if latest.get(e, MISSING) == COMPETITOR_ONLY]
    n_eng = len(engines)

    if all(c == MISSING for c in states):
        return ("absent_all", None)

    if not cited and len(comp) >= 2:
        return ("competitor_dominant", None)

    # Strong everywhere except one engine (scaled for 4–5 engines).
    if n_eng >= 3 and len(cited) >= max(3, n_eng - 1) and len(missing) == 1:
        return ("engine_specific_gap", missing[0])

    if len(cited) >= 3 and comp:
        return ("weak_engine", sorted(comp)[0])

    for e in engines:
        if prev.get(e) in (CITED_TOP, CITED_LOWER) and latest.get(e, MISSING) == COMPETITOR_ONLY:
            return ("refresh_content", e)

    # Fallback: mixed matrix (common on 4-engine scans) — brand cited or competitors show on some engines
    # but at least one engine is still MISSING. Stricter rules above often return None; this still surfaces
    # a concrete "fix this engine / footprint" row for the report card.
    if missing and (cited or comp):
        return ("extend_presence", sorted(missing)[0])

    return None


def competitor_citation_total(db: Session, latest_runs: dict[str, EngineRun | None]) -> int:
    total = 0
    for run in latest_runs.values():
        if run is None:
            continue
        n = db.scalar(
            select(func.count())
            .select_from(Citation)
            .where(
                Citation.engine_run_id == run.id,
                Citation.ownership == Ownership.COMPETITOR.value,
            )
        )
        total += int(n or 0)
    return total


def opportunity_score(
    *,
    est_volume: int | None,
    latest_states: dict[str, str],
    gap_type: str,
    competitor_cites: int,
    consecutive_gap_runs: int,
) -> float:
    n_eng = max(len(latest_states), 1)
    vol = min(math.log10(max(est_volume or 1, 1)) / 5.0, 1.0)
    miss = sum(1 for c in latest_states.values() if c == MISSING)
    comp = sum(1 for c in latest_states.values() if c == COMPETITOR_ONLY)
    gap = (miss + 0.5 * comp) / float(n_eng)
    cscore = min(competitor_cites / float(n_eng), 1.0)
    persist = min(consecutive_gap_runs / 7.0, 1.0)
    s = 0.40 * vol + 0.30 * gap + 0.20 * cscore + 0.10 * persist
    if gap_type == "absent_all" and (est_volume or 0) > 5000:
        s = max(s, 0.71)
    return round(float(s), 3)


def grade_from_score(s: float) -> str:
    if s >= 0.70:
        return "A"
    if s >= 0.40:
        return "B"
    return "C"


def heat_from_grade(g: str) -> str:
    return {"A": "HOT", "B": "WARM", "C": "COOL"}.get(g, "COOL")


TEMPLATES: dict[str, str] = {
    "absent_all": "Brand absent across all {n} engines · {vol}/mo searches",
    "competitor_dominant": "Competitor cited {comp}× · brand absent · {vol}/mo",
    "engine_specific_gap": "Cited on {cited} engines but absent from {engine_label}",
    "weak_engine": "Strong on APIs, weak on {engine_label} · {vol}/mo",
    "refresh_content": "{top_competitor} dominates on this engine · refresh content",
    "extend_presence": "Brand not visible on {engine_label} · {absent_n} of {n} engines still open · {vol}/mo demand",
}


def _top_competitor_domain(db: Session, run: EngineRun | None) -> str:
    if run is None:
        return "Competitor"
    row = db.scalar(
        select(Citation.domain)
        .where(
            Citation.engine_run_id == run.id,
            Citation.ownership == Ownership.COMPETITOR.value,
        )
        .order_by(Citation.position.asc().nulls_last())
        .limit(1)
    )
    return row or "Competitor"


def build_description(
    *,
    gap_type: str,
    engines: list[str],
    latest_states: dict[str, str],
    scope_engine: str | None,
    est_volume: int | None,
    top_competitor: str,
) -> str:
    tmpl = TEMPLATES.get(gap_type, "{gap_type}")
    n = len(engines)
    comp_count = sum(1 for e in engines if latest_states.get(e) == COMPETITOR_ONLY)
    cited_count = sum(1 for e in engines if latest_states.get(e) in (CITED_TOP, CITED_LOWER))
    vol = fmt_volume(est_volume)
    absent_n = sum(1 for e in engines if latest_states.get(e, MISSING) == MISSING)
    ctx: dict[str, Any] = {
        "n": n,
        "vol": vol,
        "comp": comp_count,
        "cited": cited_count,
        "absent_n": absent_n,
        "engine_label": engine_label(scope_engine) if scope_engine else "",
        "top_competitor": top_competitor,
        "gap_type": gap_type,
    }
    try:
        return tmpl.format(**ctx)
    except Exception:
        return tmpl


def est_volume_for_prompt(db: Session, prompt_id: UUID) -> int | None:
    m = db.get(PromptMetrics, prompt_id)
    if m and m.est_volume is not None:
        return int(m.est_volume)
    return None


def upsert_opportunity_row(
    db: Session,
    *,
    brand_id: UUID,
    prompt_id: UUID,
    gap_type: str,
    scope: str,
    grade: str,
    opportunity_score_val: float,
    description: str,
    est_volume: int | None,
) -> None:
    scope_norm = _scope_key(scope) if scope else ""
    existing = db.scalar(
        select(Opportunity).where(
            Opportunity.brand_id == brand_id,
            Opportunity.prompt_id == prompt_id,
            Opportunity.gap_type == gap_type,
            Opportunity.scope == scope_norm,
        )
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.grade = grade
        existing.opportunity_score = opportunity_score_val
        existing.description = description
        existing.est_volume = est_volume
        existing.detected_at = now
        existing.status = "open"
    else:
        db.add(
            Opportunity(
                id=uuid.uuid4(),
                brand_id=brand_id,
                prompt_id=prompt_id,
                gap_type=gap_type,
                scope=scope_norm,
                grade=grade,
                opportunity_score=opportunity_score_val,
                description=description,
                est_volume=est_volume,
                detected_at=now,
                status="open",
            )
        )


def resolve_stale_for_prompt(
    db: Session,
    brand_id: UUID,
    prompt_id: UUID,
    active_gap_type: str | None,
    active_scope: str | None,
) -> None:
    """Mark open rows for this prompt as resolved when they no longer match."""
    active_scope_norm = _scope_key(active_scope) if active_scope else ""
    rows = list(
        db.scalars(
            select(Opportunity).where(
                Opportunity.brand_id == brand_id,
                Opportunity.prompt_id == prompt_id,
                Opportunity.status == "open",
            )
        ).all()
    )
    for row in rows:
        if active_gap_type is None:
            row.status = "resolved"
            continue
        if row.gap_type == active_gap_type and row.scope == active_scope_norm:
            continue
        row.status = "resolved"


def detect_opportunities_for_brand(db: Session, brand_id: UUID) -> int:
    """Recompute opportunities for one brand. Returns number of prompts evaluated."""
    brand = db.get(Brand, brand_id)
    if not brand:
        return 0
    engines = default_engines()
    prompts = list(
        db.scalars(select(Prompt).where(Prompt.brand_id == brand_id, Prompt.enabled.is_(True))).all()
    )
    n_eval = 0
    for p in prompts:
        n_eval += 1
        latest_runs, prev_runs = _runs_latest_and_prev(db, p.id, engines)
        latest_states = {e: run_to_classifier_state(db, latest_runs.get(e)) for e in engines}
        prev_states = {e: run_to_classifier_state(db, prev_runs.get(e)) for e in engines}
        classified = classify_gap(latest_states, prev_states, engines)
        ev = est_volume_for_prompt(db, p.id)
        comp_total = competitor_citation_total(db, latest_runs)

        if classified is None:
            p.consecutive_gap_runs = 0
            resolve_stale_for_prompt(db, brand_id, p.id, None, None)
            continue

        gap_type, scope_engine = classified
        p.consecutive_gap_runs = int(p.consecutive_gap_runs or 0) + 1
        score = opportunity_score(
            est_volume=ev,
            latest_states=latest_states,
            gap_type=gap_type,
            competitor_cites=comp_total,
            consecutive_gap_runs=int(p.consecutive_gap_runs or 0),
        )
        g = grade_from_score(score)
        top_comp = _top_competitor_domain(
            db, latest_runs.get(scope_engine) if scope_engine else None
        )
        desc = build_description(
            gap_type=gap_type,
            engines=engines,
            latest_states=latest_states,
            scope_engine=scope_engine,
            est_volume=ev,
            top_competitor=top_comp,
        )
        upsert_opportunity_row(
            db,
            brand_id=brand_id,
            prompt_id=p.id,
            gap_type=gap_type,
            scope=scope_engine or "",
            grade=g,
            opportunity_score_val=score,
            description=desc,
            est_volume=ev,
        )
        resolve_stale_for_prompt(db, brand_id, p.id, gap_type, scope_engine)

    db.commit()
    _log.info("detect_opportunities brand_id=%s prompts=%s", brand_id, n_eval)
    return n_eval


def list_opportunities_for_brand(db: Session, brand_id: UUID, status: str = "open") -> list[Opportunity]:
    grade_order = case(
        (Opportunity.grade == "A", 0),
        (Opportunity.grade == "B", 1),
        else_=2,
    )
    stmt = (
        select(Opportunity)
        .where(Opportunity.brand_id == brand_id, Opportunity.status == status)
        .order_by(grade_order, Opportunity.opportunity_score.desc())
    )
    return list(db.scalars(stmt).all())
