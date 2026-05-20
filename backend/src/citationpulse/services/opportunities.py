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
    Scan,
    default_engines,
)
from citationpulse.services.demand import (
    DemandResult,
    bucket_from_volume,
    persist_demand_to_prompt,
    resolve_demand,
    score_from_volume,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Locale → DataForSEO location_code mapping (sync_prompt_volumes_for_brand)
# Full list: https://docs.dataforseo.com/v3/keywords_data/google_ads/locations/
# ---------------------------------------------------------------------------
_LOCALE_TO_LOCATION: dict[str, int] = {
    "en-us": 2840,  # United States
    "en-au": 2036,  # Australia
    "en-gb": 2826,  # United Kingdom
    "en-ca": 2124,  # Canada
    "en-nz": 2554,  # New Zealand
    "en-sg": 2702,  # Singapore
    "en-in": 2356,  # India
    "en-za": 2710,  # South Africa
    "en-ie": 2372,  # Ireland
}
_DEFAULT_LOCATION_CODE = 2840  # US fallback

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
    demand_score: float | None = None,
    demand_bucket: str | None = None,
) -> float:
    """Final 0..1 opportunity score.

    Formula (per spec):
        0.40 * demand
        0.30 * gap
        0.20 * competitor citation share
        0.10 * persistence (consecutive gap runs)

    ``demand`` comes from the precomputed ``Prompt.demand_score`` column.
    If the caller doesn't have a resolved demand value yet (older rows,
    detector running before the first refresh_demand pass) we fall back
    to ``log10(est_volume)/5`` so historical rows keep grading sensibly.

    Special rule: ``gap_type == "absent_all"`` AND ``demand_bucket == "high"``
    forces grade A (minimum score = 0.71). High-volume absences always win
    a slot at the top of the dashboard.
    """
    n_eng = max(len(latest_states), 1)
    # Resolve demand component: prefer precomputed demand_score over raw volume.
    if demand_score is not None:
        demand = max(0.0, min(float(demand_score), 1.0))
    else:
        demand = score_from_volume(est_volume)
    miss = sum(1 for c in latest_states.values() if c == MISSING)
    comp = sum(1 for c in latest_states.values() if c == COMPETITOR_ONLY)
    gap = (miss + 0.5 * comp) / float(n_eng)
    cscore = min(competitor_cites / float(n_eng), 1.0)
    persist = min(consecutive_gap_runs / 7.0, 1.0)
    s = 0.40 * demand + 0.30 * gap + 0.20 * cscore + 0.10 * persist

    # New rule: bucket-based grade A floor for absent_all.
    bucket = (demand_bucket or bucket_from_volume(est_volume) or "").lower()
    if gap_type == "absent_all" and bucket == "high":
        s = max(s, 0.71)
    # Legacy rule (kept for back-compat): absolute volume override.
    elif gap_type == "absent_all" and (est_volume or 0) > 5000:
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


def demand_pill_from_bucket(bucket: str | None) -> str:
    """Map a demand bucket onto the UI pill copy (HIGH/MEDIUM/LOW/UNKNOWN).

    The spec asks us to NEVER show raw search volume in the row UI — only
    in the tooltip / details. The pill is what the row badge renders.
    """
    if not bucket:
        return "UNKNOWN"
    b = bucket.strip().lower()
    if b == "high":
        return "HIGH"
    if b == "medium":
        return "MEDIUM"
    if b == "low":
        return "LOW"
    return "UNKNOWN"


TEMPLATES: dict[str, str] = {
    "absent_all": "Brand absent across all {n} engines · {vol}/mo searches",
    "competitor_dominant": "Competitor cited {comp}× · brand absent · {vol}/mo",
    "engine_specific_gap": "Cited on {cited} engines but absent from {engine_label}",
    "weak_engine": "Strong on other models, weaker on {engine_label} · {vol}/mo",
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


def sync_prompt_volumes_for_brand(db: Session, brand_id: UUID) -> int:
    """Fetch DataForSEO Google Ads monthly search volumes for all brand prompts.

    Groups prompts by locale, calls DataForSEO once per locale group, and upserts
    the avg ``search_volume`` into ``prompt_metrics``. Silently skips when DataForSEO
    is not configured or returns no data — the opportunity scorer falls back to
    ``est_volume=None`` which still produces valid (lower) scores.

    Returns the number of prompts whose volume was updated. Backported from
    apps/api/services/opportunities.py so the Railway-deployed backend tree
    can populate the "Est. monthly searches" column in the funnel report.
    """
    import re

    from citationpulse.services.dataforseo_keywords import (
        DataForSEOError,
        dataforseo_configured,
        fetch_google_ads_search_volumes,
    )

    if not dataforseo_configured():
        _log.debug("sync_prompt_volumes: DataForSEO not configured, skipping")
        return 0

    prompts = list(
        db.scalars(select(Prompt).where(Prompt.brand_id == brand_id, Prompt.enabled.is_(True))).all()
    )
    if not prompts:
        return 0

    # Group by locale so we make one DataForSEO call per geo (location_code).
    by_locale: dict[str, list[Prompt]] = defaultdict(list)
    for p in prompts:
        by_locale[(p.locale or "en-US").strip()].append(p)

    updated = 0
    now = datetime.now(timezone.utc)

    # DataForSEO rejects question marks and a handful of punctuation chars in
    # the `keywords` array. Strip them and collapse extra whitespace so a prompt
    # like "what is the best seo agency?" still gets a volume back.
    _KW_BAD = re.compile(r"[?!;:\"'()\[\]{}<>@#$%^&*\\|~`]")

    def _clean_keyword(text: str) -> str:
        cleaned = _KW_BAD.sub(" ", text[:700])
        return " ".join(cleaned.split())

    for locale, locale_prompts in by_locale.items():
        # Normalise "en_AU" / "EN-au" → "en-au" for lookup
        loc_lower = locale.lower().replace("_", "-")
        location_code = _LOCALE_TO_LOCATION.get(loc_lower, _DEFAULT_LOCATION_CODE)
        language_code = loc_lower.split("-")[0] or "en"

        keywords = [_clean_keyword(p.text) for p in locale_prompts]
        try:
            rows = fetch_google_ads_search_volumes(
                keywords,
                location_code=location_code,
                language_code=language_code,
            )
        except DataForSEOError as exc:
            _log.warning(
                "sync_prompt_volumes DataForSEO error brand_id=%s locale=%s: %s",
                brand_id,
                locale,
                exc,
            )
            continue

        vol_map: dict[str, int] = {}
        for row in rows:
            kw = (row.get("keyword") or "").strip().lower()
            sv = row.get("search_volume")
            if kw and isinstance(sv, (int, float)) and sv >= 0:
                vol_map[kw] = int(sv)

        for p in locale_prompts:
            kw_key = _clean_keyword(p.text).lower()
            volume = vol_map.get(kw_key)
            if volume is None:
                # Fuzzy: try a prefix-overlap match when the API echoed a slightly
                # different normalisation of our keyword.
                for k, v in vol_map.items():
                    if kw_key.startswith(k[:40]) or k.startswith(kw_key[:40]):
                        volume = v
                        break
            if volume is None:
                continue
            existing = db.get(PromptMetrics, p.id)
            if existing:
                existing.est_volume = volume
                existing.updated_at = now
            else:
                db.add(PromptMetrics(prompt_id=p.id, est_volume=volume, updated_at=now))
            updated += 1

    if updated:
        db.commit()
        _log.info("sync_prompt_volumes brand_id=%s updated=%d prompts", brand_id, updated)

    return updated


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


def engines_for_brand_opportunities(db: Session, brand_id: UUID) -> list[str]:
    """Engines from the brand's newest scan — matches rows actually enqueued for that funnel.

    Using ``default_engines()`` alone can mis-size the classifier vs a scan that ran a subset
    of engines (or a different order), which yields no gap match in production while dev looks fine.
    """
    scan = db.scalar(
        select(Scan).where(Scan.brand_id == brand_id).order_by(Scan.created_at.desc()).limit(1)
    )
    if scan and scan.engines:
        out = [str(e).strip() for e in scan.engines if str(e).strip()]
        if out:
            return out
    return list(default_engines())


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


def _ensure_demand(db: Session, prompt: Prompt) -> DemandResult:
    """Return a non-null DemandResult, computing & persisting it if missing.

    Detect-opportunities is allowed to back-fill demand for a single prompt
    if the weekly refresh hasn't run yet. The Redis cache means this is
    cheap even when 100s of prompts hit the same code path during a fresh
    deploy.
    """
    if prompt.demand_score is not None and prompt.demand_bucket:
        return DemandResult(
            score=float(prompt.demand_score),
            bucket=str(prompt.demand_bucket),
            source=str(prompt.demand_source or "literal"),
            variant=prompt.demand_variant,
            raw_volume=prompt.demand_raw_volume,
        )
    result = resolve_demand(db, prompt)
    persist_demand_to_prompt(prompt, result)
    return result


def detect_opportunities_for_brand(
    db: Session,
    brand_id: UUID,
    *,
    engines_override: list[str] | None = None,
) -> int:
    """Recompute opportunities for one brand. Returns number of prompts evaluated.

    Order of work per prompt:
        1. Resolve latest/prev cell states from EngineRun history.
        2. Ensure precomputed demand exists (back-fill via 4-step fallback if not).
        3. Classify gap. None → mark any open opportunity as resolved.
        4. Score using demand_score (preferred) with absent_all + high-bucket floor.
        5. Upsert keyed by (brand_id, prompt_id, gap_type, scope).
        6. Mark stale open rows as resolved so the audit trail stays intact.
    """
    brand = db.get(Brand, brand_id)
    if not brand:
        return 0
    if engines_override is not None:
        engines = [str(e).strip() for e in engines_override if str(e).strip()]
        if not engines:
            engines = engines_for_brand_opportunities(db, brand_id)
    else:
        engines = engines_for_brand_opportunities(db, brand_id)
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

        # Keep est_volume for back-compat (column still exists on opportunities + UI tooltip).
        ev = p.demand_raw_volume if p.demand_raw_volume is not None else est_volume_for_prompt(db, p.id)
        comp_total = competitor_citation_total(db, latest_runs)

        if classified is None:
            p.consecutive_gap_runs = 0
            resolve_stale_for_prompt(db, brand_id, p.id, None, None)
            continue

        demand = _ensure_demand(db, p)
        gap_type, scope_engine = classified
        p.consecutive_gap_runs = int(p.consecutive_gap_runs or 0) + 1
        score = opportunity_score(
            est_volume=ev,
            latest_states=latest_states,
            gap_type=gap_type,
            competitor_cites=comp_total,
            consecutive_gap_runs=int(p.consecutive_gap_runs or 0),
            demand_score=demand.score,
            demand_bucket=demand.bucket,
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


def list_opportunities_for_brand(
    db: Session,
    brand_id: UUID,
    status: str = "open",
    *,
    grade: str | None = None,
    gap_type: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Opportunity]:
    """Return opportunities sorted A→B→C, then by score DESC.

    Optional filters:
      grade: ``"A"`` | ``"B"`` | ``"C"`` — exact grade match
      gap_type: e.g. ``"absent_all"`` | ``"competitor_dominant"``
      limit/offset: pagination knobs (omit for "all rows")
    """
    grade_order = case(
        (Opportunity.grade == "A", 0),
        (Opportunity.grade == "B", 1),
        else_=2,
    )
    stmt = (
        select(Opportunity)
        .where(Opportunity.brand_id == brand_id, Opportunity.status == status)
        .order_by(grade_order, Opportunity.opportunity_score.desc(), Opportunity.detected_at.desc())
    )
    if grade:
        stmt = stmt.where(Opportunity.grade == grade.upper())
    if gap_type:
        stmt = stmt.where(Opportunity.gap_type == gap_type)
    if offset:
        stmt = stmt.offset(int(offset))
    if limit is not None:
        stmt = stmt.limit(int(limit))
    return list(db.scalars(stmt).all())


def count_opportunities_for_brand(
    db: Session,
    brand_id: UUID,
    status: str = "open",
    *,
    grade: str | None = None,
    gap_type: str | None = None,
) -> int:
    """Total matching opportunities — used for paginated API responses."""
    stmt = (
        select(func.count())
        .select_from(Opportunity)
        .where(Opportunity.brand_id == brand_id, Opportunity.status == status)
    )
    if grade:
        stmt = stmt.where(Opportunity.grade == grade.upper())
    if gap_type:
        stmt = stmt.where(Opportunity.gap_type == gap_type)
    return int(db.scalar(stmt) or 0)
