from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from citationpulse.core.config import get_settings
from citationpulse.services.llm_router import openrouter_configured
from citationpulse.models.domain import (
    Brand,
    Citation,
    EngineRun,
    EngineType,
    Ownership,
    Prompt,
    RunStatus,
    Scan,
    Tenant,
    default_engines,
)
from citationpulse.services.events import publish_scan_event

ANON_TENANT_MARKER = "anonymous_scans"
_log = logging.getLogger(__name__)


# All supported engines are routed through OpenRouter, so a single API key
# enables all of them.
_LLM_ENGINES: frozenset[str] = frozenset(
    {
        EngineType.CHATGPT.value,
        EngineType.CLAUDE.value,
        EngineType.GEMINI.value,
        EngineType.PERPLEXITY.value,
    }
)


def available_engines(requested: list[str] | None = None) -> list[str]:
    """Filter engines to those that can actually run given current config.

    With OpenRouter as the unified gateway, all supported engines share a
    single `OPENROUTER_API_KEY`. If the key is missing we drop those engines
    from the requested list.

    Strategy:
      * Start from `requested` if the caller passed one, else `default_engines()`.
      * Drop LLM engines if `OPENROUTER_API_KEY` is empty.
      * If filtering would leave us with nothing, fall back to the unfiltered
        list so the scan still runs and the UI surfaces visible "missing key"
        errors per engine instead of silently producing an empty matrix.
    """
    base = list(requested) if requested else default_engines()
    settings = get_settings()
    has_openrouter = openrouter_configured(settings)
    kept: list[str] = []
    for e in base:
        # Product scans use OpenRouter-backed engines only; Google AI Overviews (Playwright) is not required.
        if e == EngineType.GOOGLE_AIO.value:
            continue
        if e in _LLM_ENGINES:
            if has_openrouter:
                kept.append(e)
            continue
        kept.append(e)
    return kept or base


def get_or_create_anonymous_tenant(db: Session) -> Tenant:
    t = db.scalar(select(Tenant).where(Tenant.settings.contains({"kind": ANON_TENANT_MARKER})))
    if t:
        return t
    t = Tenant(
        name="Public scans",
        plan="saas",
        settings={"kind": ANON_TENANT_MARKER},
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _engine_value(engine: EngineType | str) -> str:
    return engine.value if isinstance(engine, EngineType) else str(engine)


def _run_fully_processed(db: Session, run: EngineRun) -> bool:
    """A run is terminal once the engine call has finished (ok or error).

    Citation ownership/embeddings are applied inline in ``run_engine_task`` before
    the scan can complete, so completed scans already reflect brand/competitor cells.
    """
    return run.status in (RunStatus.OK.value, RunStatus.ERROR.value)


def count_terminal_runs_for_scan(db: Session, scan_id: UUID) -> tuple[int, int]:
    """Returns (terminal_count, total_count)."""
    runs = list(db.scalars(select(EngineRun).where(EngineRun.scan_id == scan_id)).all())
    total = len(runs)
    terminal = sum(1 for r in runs if _run_fully_processed(db, r))
    return terminal, total


def expected_engine_runs_for_scan(db: Session, scan: Scan) -> int:
    """Rows we expect after fan-out: enabled prompts × scan engines."""
    n_prompts = (
        db.scalar(
            select(func.count())
            .select_from(Prompt)
            .where(Prompt.brand_id == scan.brand_id, Prompt.enabled.is_(True))
        )
        or 0
    )
    eng_list = list(scan.engines) if scan.engines else default_engines()
    return n_prompts * len(eng_list)


def compute_scan_score(db: Session, scan_id: UUID) -> int:
    """Share of (prompt, engine) cells with brand citation vs total cells."""
    runs = db.scalars(select(EngineRun).where(EngineRun.scan_id == scan_id)).all()
    if not runs:
        return 0
    cited = 0
    for run in runs:
        if run.status != RunStatus.OK.value:
            continue
        has_brand = (
            db.scalar(
                select(func.count())
                .select_from(Citation)
                .where(
                    Citation.engine_run_id == run.id,
                    Citation.ownership == Ownership.BRAND.value,
                )
            )
            or 0
        )
        if int(has_brand) > 0:
            cited += 1
    return int(round(100 * cited / max(1, len(runs))))


def maybe_complete_scan(db: Session, scan_id: UUID) -> None:
    scan = db.get(Scan, scan_id)
    if not scan:
        return
    expected = expected_engine_runs_for_scan(db, scan)
    terminal, total = count_terminal_runs_for_scan(db, scan_id)
    # Do not complete until every scheduled engine×prompt run exists (fan-out finished)
    # and each run has reached a terminal state.
    if expected > 0 and total < expected:
        return
    if total == 0 or terminal < total:
        return
    new_score = compute_scan_score(db, scan_id)
    was_new = scan.status != "completed"
    prev_score = scan.score_overall
    scan.status = "completed"
    if scan.completed_at is None:
        scan.completed_at = datetime.now(timezone.utc)
    scan.score_overall = new_score
    db.commit()
    if was_new or prev_score != new_score:
        publish_scan_event(
            str(scan.id),
            {"type": "scan.completed", "score": scan.score_overall or 0},
        )
    # Funnel report reads `opportunities` from the DB — populate as soon as the scan finishes
    # (same classifier as nightly `detect_opportunities`; Celery beat still refreshes later).
    brand_id_for_detect = scan.brand_id
    engines_ov = list(scan.engines) if scan.engines else None
    if was_new and brand_id_for_detect:
        try:
            from citationpulse.services.opportunities import (
                detect_opportunities_for_brand,
                sync_prompt_volumes_for_brand,
            )

            # Fetch DataForSEO keyword volumes before scoring so est_volume is populated.
            sync_prompt_volumes_for_brand(db, brand_id_for_detect)
            detect_opportunities_for_brand(db, brand_id_for_detect, engines_override=engines_ov)
        except Exception:
            _log.exception(
                "detect_opportunities_for_brand after scan completion failed scan_id=%s brand_id=%s",
                scan_id,
                brand_id_for_detect,
            )
    elif brand_id_for_detect and scan.status == "completed" and not was_new:
        # First completion hook can fail (transient DB) or run before late normalisation. Later
        # `maybe_complete_scan` calls skip `was_new`; backfill when we still have zero open rows.
        try:
            from citationpulse.services.opportunities import (
                detect_opportunities_for_brand,
                list_opportunities_for_brand,
                sync_prompt_volumes_for_brand,
            )

            if not list_opportunities_for_brand(db, brand_id_for_detect, status="open"):
                sync_prompt_volumes_for_brand(db, brand_id_for_detect)
                detect_opportunities_for_brand(db, brand_id_for_detect, engines_override=engines_ov)
        except Exception:
            _log.exception(
                "detect_opportunities_for_brand backfill failed scan_id=%s brand_id=%s",
                scan_id,
                brand_id_for_detect,
            )


def _cell_citations_payload(cites: list[Citation], limit: int = 8) -> list[dict[str, object]]:
    """Serialize the top N citations of a cell for the UI.

    Sort order: brand > competitor > neutral, then by `position` ASC. This
    mirrors what the user wants to see first ("did my brand show up?") while
    still surfacing the rest of the cited URLs so the report is never empty
    when the engine actually returned data.
    """
    rank = {Ownership.BRAND.value: 0, Ownership.COMPETITOR.value: 1, Ownership.NEUTRAL.value: 2}
    sorted_cites = sorted(
        cites,
        key=lambda c: (rank.get(c.ownership, 9), c.position if c.position is not None else 999),
    )
    out: list[dict[str, object]] = []
    for c in sorted_cites[:limit]:
        out.append(
            {
                "url": c.url,
                "ownership": c.ownership,
                "position": int(c.position) if c.position is not None else None,
                "snippet": (c.snippet or "")[:200] or None,
            }
        )
    return out


def cell_status_for_run(db: Session, run: EngineRun) -> dict[str, object]:
    eng = _engine_value(run.engine)
    base: dict[str, object] = {"promptId": str(run.prompt_id), "engine": eng}
    if run.status == RunStatus.QUEUED.value:
        return {**base, "status": "queued", "citationsCount": 0, "citations": []}
    if run.status == RunStatus.RUNNING.value:
        return {**base, "status": "running", "citationsCount": 0, "citations": []}
    if run.status == RunStatus.ERROR.value:
        err = (run.error_message or "").strip()
        return {
            **base,
            "status": "error",
            "citationsCount": 0,
            "citations": [],
            "errorMessage": err[:500] if err else None,
        }
    if run.status != RunStatus.OK.value:
        return {**base, "status": "none", "citationsCount": 0, "citations": []}

    cites = db.scalars(select(Citation).where(Citation.engine_run_id == run.id)).all()
    citations_payload = _cell_citations_payload(list(cites))
    enriched: dict[str, object] = {
        **base,
        "citationsCount": len(cites),
        "citations": citations_payload,
    }

    if not cites:
        # Engine ran successfully but returned no URLs — surface that explicitly.
        return {**enriched, "status": "none"}

    brand_cites = [c for c in cites if c.ownership == Ownership.BRAND.value]
    comp_cites = [c for c in cites if c.ownership == Ownership.COMPETITOR.value]

    if brand_cites:
        positions = [c.position for c in brand_cites if c.position is not None]
        pos = min(positions) if positions else None
        out: dict[str, object] = {**enriched, "status": "cited"}
        if pos is not None:
            out["position"] = int(pos)
        return out
    if comp_cites:
        return {**enriched, "status": "comp"}
    # All citations are neutral — the engine answered with URLs but none were
    # the brand or a registered competitor. Mark as `none` (terminal) so the
    # UI can still display the cited URLs from the `citations` payload.
    return {**enriched, "status": "none"}


def engine_progress_event(db: Session, scan_id: UUID, engine: str) -> dict[str, object]:
    try:
        et = EngineType(engine)
    except ValueError:
        return {"type": "engine.progress", "engine": engine, "done": 0, "total": 0}
    runs = list(
        db.scalars(
            select(EngineRun).where(EngineRun.scan_id == scan_id, EngineRun.engine == et)
        ).all()
    )
    total = len(runs)
    done = sum(1 for r in runs if _run_fully_processed(db, r))
    return {"type": "engine.progress", "engine": engine, "done": int(done), "total": int(total)}


def publish_cell_update(db: Session, run: EngineRun) -> None:
    if not run.scan_id:
        return
    cell = cell_status_for_run(db, run)
    publish_scan_event(
        str(run.scan_id),
        {"type": "cell.update", **cell},
    )
    ev = engine_progress_event(db, run.scan_id, _engine_value(run.engine))
    publish_scan_event(str(run.scan_id), ev)


def _engines_for_report_columns(
    requested: list[str],
    scan_status: str,
) -> list[str]:
    """Column engines for the scan matrix / snapshot.

    While the scan is running we keep the full requested list so the user sees
    every column animate. Once the scan is terminal, we still return the full
    requested list so columns match what was scheduled (including engines whose
    runs all errored — those cells use ``status: "error"`` in ``cell_status_for_run``).
    """
    if scan_status not in {"completed", "failed"}:
        return requested
    return list(requested)


def build_scan_snapshot(db: Session, scan: Scan) -> dict[str, object]:
    brand = db.get(Brand, scan.brand_id)
    prompts = list(db.scalars(select(Prompt).where(Prompt.brand_id == scan.brand_id)).all())
    runs = list(db.scalars(select(EngineRun).where(EngineRun.scan_id == scan.id)).all())

    requested_engines = list(scan.engines) if scan.engines else default_engines()
    visible_engines = _engines_for_report_columns(requested_engines, scan.status)
    visible_set = set(visible_engines)

    cells: list[dict[str, object]] = []
    for run in runs:
        engine_key = run.engine.value if isinstance(run.engine, EngineType) else str(run.engine)
        if engine_key not in visible_set:
            continue
        cells.append(cell_status_for_run(db, run))
    per_engine: dict[str, dict[str, int]] = {}
    for e in visible_engines:
        ev = engine_progress_event(db, scan.id, e)
        if isinstance(ev.get("done"), int) and isinstance(ev.get("total"), int):
            per_engine[str(ev["engine"])] = {"done": ev["done"], "total": ev["total"]}
    return {
        "scan_id": str(scan.id),
        "status": scan.status,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "submitted_url": scan.submitted_url,
        "locale": scan.locale,
        "engines": visible_engines,
        "score_overall": scan.score_overall,
        "share_public": scan.share_public,
        "share_token": scan.share_token,
        "brand": (
            {
                "id": str(brand.id),
                "name": brand.name,
                "domains": list(brand.domains or []),
            }
            if brand
            else None
        ),
        "prompts": [{"id": str(p.id), "text": p.text, "locale": p.locale} for p in prompts],
        "matrix": {"cells": cells},
        "progress": {"per_engine": per_engine},
    }


def build_scan_report(db: Session, scan: Scan) -> dict[str, object]:
    snap = build_scan_snapshot(db, scan)
    brand = db.get(Brand, scan.brand_id)
    gaps: list[dict[str, object]] = []
    if brand:
        from citationpulse.services.gaps import detect_gaps

        for g in detect_gaps(db, brand.tenant_id, brand.id):
            grade = "B"
            if g.score >= 0.66:
                grade = "A"
            elif g.score <= 0.33:
                grade = "C"
            gaps.append(
                {
                    "prompt_id": str(g.prompt_id),
                    "score": g.score,
                    "reason": g.reason,
                    "grade": grade,
                }
            )
    from citationpulse.services.sov import compute_sov

    breakdown = None
    if brand:
        s = compute_sov(db, brand.tenant_id, brand.id, days=30)
        breakdown = {
            "brand_share": s.brand_share,
            "competitor_share": s.competitor_share,
            "third_party_share": s.third_party_share,
            "neutral_share": s.neutral_share,
        }
    competitors: list[dict[str, str]] = []
    if brand and brand.competitors:
        for cid in brand.competitors:
            cb = db.get(Brand, cid)
            if cb:
                competitors.append({"id": str(cb.id), "name": cb.name, "domains": ",".join(cb.domains or [])})

    opportunities: list[dict[str, object]] = []
    if brand:
        from citationpulse.services.opportunities import (
            detect_opportunities_for_brand,
            heat_from_grade,
            list_opportunities_for_brand,
        )

        rows = list_opportunities_for_brand(db, brand.id, status="open")
        if not rows and scan.status == "completed":
            try:
                from citationpulse.services.opportunities import sync_prompt_volumes_for_brand

                eng_ov = list(scan.engines) if scan.engines else None
                sync_prompt_volumes_for_brand(db, brand.id)
                detect_opportunities_for_brand(db, brand.id, engines_override=eng_ov)
                rows = list_opportunities_for_brand(db, brand.id, status="open")
            except Exception:
                _log.exception(
                    "detect_opportunities_for_brand during build_scan_report failed scan_id=%s brand_id=%s",
                    scan.id,
                    brand.id,
                )
        for o in rows[:50]:
            pr = db.get(Prompt, o.prompt_id)
            title = (pr.text if pr else "")[:512] or "(prompt)"
            scope_val = o.scope if (o.scope or "").strip() else None
            opportunities.append(
                {
                    "id": str(o.id),
                    "brand_id": str(o.brand_id),
                    "prompt_id": str(o.prompt_id),
                    "title": title,
                    "gap_type": o.gap_type,
                    "scope": scope_val,
                    "grade": o.grade,
                    "heat": heat_from_grade(o.grade),
                    "opportunity_score": float(o.opportunity_score),
                    "description": o.description,
                    "est_volume": o.est_volume,
                    "status": o.status,
                    "detected_at": o.detected_at.isoformat() if o.detected_at else None,
                }
            )

    return {
        **snap,
        "gaps": gaps[:50],
        "breakdown": breakdown,
        "competitors": competitors,
        "opportunities": opportunities,
    }
