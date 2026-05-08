from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from citationpulse.models.domain import Brand, Citation, EngineRun, Ownership, Prompt


@dataclass
class SoVResult:
    brand_share: float
    competitor_share: float
    third_party_share: float
    neutral_share: float


def compute_sov(
    db: Session,
    tenant_id: UUID,
    brand_id: UUID,
    days: int = 30,
) -> SoVResult:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(Citation.ownership, func.count())
        .join(EngineRun, Citation.engine_run_id == EngineRun.id)
        .join(Prompt, EngineRun.prompt_id == Prompt.id)
        .join(Brand, Prompt.brand_id == Brand.id)
        .where(Brand.tenant_id == tenant_id, Brand.id == brand_id)
        .where(EngineRun.finished_at.is_not(None))
        .where(EngineRun.finished_at >= since)
        .group_by(Citation.ownership)
    )
    counts: dict[str, int] = {}
    for own, cnt in db.execute(stmt):
        counts[str(own)] = int(cnt)
    total = sum(counts.values()) or 1
    neutral = counts.get(Ownership.NEUTRAL.value, 0) + counts.get("unknown", 0)
    return SoVResult(
        brand_share=counts.get(Ownership.BRAND.value, 0) / total,
        competitor_share=counts.get(Ownership.COMPETITOR.value, 0) / total,
        third_party_share=counts.get(Ownership.THIRD_PARTY.value, 0) / total,
        neutral_share=neutral / total,
    )
