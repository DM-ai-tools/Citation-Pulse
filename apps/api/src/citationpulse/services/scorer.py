from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from citationpulse.models.domain import Brand, Citation, EngineRun, Prompt


def trend_citations_per_day(db: Session, tenant_id: UUID, brand_id: UUID, days: int = 14) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(func.date_trunc("day", Citation.created_at).label("d"), func.count())
        .join(EngineRun, Citation.engine_run_id == EngineRun.id)
        .join(Prompt, EngineRun.prompt_id == Prompt.id)
        .join(Brand, Prompt.brand_id == Brand.id)
        .where(Brand.tenant_id == tenant_id, Brand.id == brand_id, Citation.created_at >= since)
        .group_by("d")
        .order_by("d")
    )
    return [{"day": str(row[0]), "count": int(row[1])} for row in db.execute(stmt)]
