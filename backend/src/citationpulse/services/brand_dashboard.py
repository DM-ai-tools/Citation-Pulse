"""Aggregate dashboard views for a brand (prompt × engine matrix, engine mix)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from citationpulse.models.domain import Brand, Citation, EngineRun, EngineType, Prompt
from citationpulse.models.domain import default_engines
from citationpulse.services.scans_flow import cell_status_for_run


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def parse_range_days(range_param: str) -> int:
    if range_param.endswith("d"):
        try:
            return int(range_param[:-1] or "30")
        except ValueError:
            return 30
    return 30


def latest_runs_per_prompt_engine(
    db: Session,
    brand: Brand,
    days: int,
) -> list[EngineRun]:
    """One EngineRun per (prompt, engine), preferring the latest by created_at."""
    since = _since(days)
    stmt = (
        select(EngineRun)
        .join(Prompt, EngineRun.prompt_id == Prompt.id)
        .where(Prompt.brand_id == brand.id, EngineRun.created_at >= since)
        .order_by(EngineRun.created_at.desc())
    )
    runs = list(db.scalars(stmt).all())
    seen: set[tuple[UUID, str]] = set()
    out: list[EngineRun] = []
    for r in runs:
        eng = r.engine.value if isinstance(r.engine, EngineType) else str(r.engine)
        key = (r.prompt_id, eng)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_brand_matrix_payload(db: Session, tenant_id: UUID, brand_id: UUID, days: int) -> dict:
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant_id:
        return {}
    prompts = list(db.scalars(select(Prompt).where(Prompt.brand_id == b.id).order_by(Prompt.created_at.asc())).all())
    runs = latest_runs_per_prompt_engine(db, b, days)
    cells = [cell_status_for_run(db, r) for r in runs]
    engines = default_engines()
    return {
        "brand_id": str(b.id),
        "range_days": days,
        "prompts": [{"id": str(p.id), "text": p.text, "locale": p.locale} for p in prompts],
        "engines": engines,
        "matrix": {"cells": cells},
    }


def citation_counts_by_engine(
    db: Session,
    tenant_id: UUID,
    brand_id: UUID,
    days: int,
) -> dict:
    """Count citations per engine in the window (finished runs only)."""
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant_id:
        return {"range_days": days, "items": [], "total": 0}
    since = _since(days)
    stmt = (
        select(EngineRun.engine, func.count(Citation.id))
        .select_from(Citation)
        .join(EngineRun, Citation.engine_run_id == EngineRun.id)
        .join(Prompt, EngineRun.prompt_id == Prompt.id)
        .join(Brand, Prompt.brand_id == Brand.id)
        .where(Brand.id == b.id, Brand.tenant_id == tenant_id)
        .where(EngineRun.finished_at.is_not(None))
        .where(EngineRun.finished_at >= since)
        .group_by(EngineRun.engine)
    )
    raw: dict[str, int] = {}
    for eng, cnt in db.execute(stmt):
        key = eng.value if isinstance(eng, EngineType) else str(eng)
        raw[key] = int(cnt)
    # Include all default engines so the chart has stable categories.
    items: list[dict[str, object]] = []
    for e in default_engines():
        c = raw.get(e, 0)
        items.append({"engine": e, "citations": c})
    total = sum(raw.values())
    return {"range_days": days, "items": items, "total": total}
