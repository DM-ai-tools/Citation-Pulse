from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from citationpulse.core.config import get_settings
from citationpulse.models.domain import Brand, Citation, EngineRun, Prompt, RunStatus


@dataclass
class GapItem:
    prompt_id: UUID
    score: float
    reason: str


def detect_gaps(db: Session, tenant_id: UUID, brand_id: UUID) -> list[GapItem]:
    """Prompts where brand never cited in successful runs but competitors are (heuristic)."""
    n = get_settings().gap_absence_run_threshold
    gaps: list[GapItem] = []
    prompts = (
        db.execute(select(Prompt).where(Prompt.brand_id == brand_id, Prompt.enabled.is_(True)))
        .scalars()
        .all()
    )
    brand = db.get(Brand, brand_id)
    if not brand or brand.tenant_id != tenant_id:
        return []
    for p in prompts:
        runs = (
            db.execute(
                select(EngineRun).where(
                    EngineRun.prompt_id == p.id,
                    EngineRun.status == RunStatus.OK.value,
                )
            )
            .scalars()
            .all()
        )
        if len(runs) < n:
            continue
        brand_hits = 0
        comp_hits = 0
        for run in runs:
            bc = db.execute(
                select(func.count())
                .select_from(Citation)
                .where(
                    Citation.engine_run_id == run.id,
                    Citation.ownership == "brand",
                )
            ).scalar_one()
            cc = db.execute(
                select(func.count())
                .select_from(Citation)
                .where(
                    Citation.engine_run_id == run.id,
                    Citation.ownership == "competitor",
                )
            ).scalar_one()
            brand_hits += int(bc)
            comp_hits += int(cc)
        if comp_hits > 0 and brand_hits == 0:
            gaps.append(
                GapItem(
                    prompt_id=p.id,
                    score=min(1.0, comp_hits / max(1, len(runs))),
                    reason="competitor_cited_without_brand_across_runs",
                )
            )
    return gaps
