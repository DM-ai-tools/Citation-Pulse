from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from citationpulse.api.deps import CurrentTenant, DbSession, get_auth_context
from citationpulse.tasks.geo import fan_out_brand
from citationpulse.models.domain import Alert, AlertRule, Brand, Citation, EngineRun, EngineType, Opportunity, Prompt
from citationpulse.schemas.brands import (
    AlertFeedItem,
    AlertRuleCreate,
    AlertRuleRead,
    BrandCreate,
    BrandRead,
    CitationRead,
    GapRead,
    GapAnalysisRead,
    OpportunityDetailRead,
    OpportunityRead,
    PromptBulkCreate,
    PromptRead,
    RunCreate,
    RunRead,
    SoVRead,
)
from citationpulse.services.brand_dashboard import (
    build_brand_matrix_payload,
    citation_counts_by_engine,
    parse_range_days,
)
from citationpulse.services.gaps import detect_gaps
from citationpulse.services.opportunities import heat_from_grade, list_opportunities_for_brand
from citationpulse.services.rate_limit import allow_ad_hoc_run
from citationpulse.services.scorer import trend_citations_per_day
from citationpulse.services.sov import compute_sov
from citationpulse.services.sov_entities import (
    entity_weekly_share_trend,
    multi_entity_weekly_share_trend,
    multientity_sov_by_engine,
)

router = APIRouter(dependencies=[Depends(get_auth_context)])


@router.get("/brands", response_model=list[BrandRead])
def list_brands(db: DbSession, tenant: CurrentTenant):
    rows = db.scalars(select(Brand).where(Brand.tenant_id == tenant.id).order_by(Brand.created_at.desc())).all()
    return list(rows)


@router.post("/brands", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
def create_brand(body: BrandCreate, db: DbSession, tenant: CurrentTenant):
    b = Brand(
        tenant_id=tenant.id,
        name=body.name,
        domains=body.domains,
        competitors=list(body.competitor_brand_ids),
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@router.get("/brands/{brand_id}", response_model=BrandRead)
def get_brand(brand_id: UUID, db: DbSession, tenant: CurrentTenant):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    return b


@router.post("/brands/{brand_id}/prompts", response_model=list[PromptRead])
def add_prompts(brand_id: UUID, body: PromptBulkCreate, db: DbSession, tenant: CurrentTenant):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    out: list[Prompt] = []
    for p in body.prompts:
        row = Prompt(
            brand_id=b.id,
            text=p.text,
            locale=p.locale,
            intent=p.intent,
            enabled=p.enabled,
        )
        db.add(row)
        out.append(row)
    db.commit()
    for r in out:
        db.refresh(r)
    return out


@router.get("/brands/{brand_id}/prompts", response_model=list[PromptRead])
def list_prompts(brand_id: UUID, db: DbSession, tenant: CurrentTenant):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    return list(db.scalars(select(Prompt).where(Prompt.brand_id == b.id)).all())


@router.post("/brands/{brand_id}/runs")
def trigger_runs(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    body: RunCreate | None = None,
):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    if not allow_ad_hoc_run(str(b.id)):
        raise HTTPException(status_code=429, detail="Rate limited — try again later")
    engines = [e.value for e in EngineType]
    if body and body.engines:
        engines = [e for e in body.engines if e in engines]
    fan_out_brand.delay(str(b.id), engines)
    return {"status": "enqueued", "brand_id": str(b.id), "engines": engines}


@router.get("/brands/{brand_id}/runs", response_model=list[RunRead])
def list_runs(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    range: str = Query("30d", alias="range"),
):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    days = parse_range_days(range)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(EngineRun)
        .join(Prompt, EngineRun.prompt_id == Prompt.id)
        .where(Prompt.brand_id == b.id, EngineRun.created_at >= since)
        .order_by(EngineRun.created_at.desc())
    )
    runs = list(db.scalars(stmt).all())
    out: list[RunRead] = []
    for r in runs:
        out.append(
            RunRead(
                id=r.id,
                prompt_id=r.prompt_id,
                engine=r.engine.value if hasattr(r.engine, "value") else str(r.engine),
                status=r.status,
                started_at=r.started_at,
                finished_at=r.finished_at,
                cost_usd=str(r.cost_usd) if r.cost_usd is not None else None,
            )
        )
    return out


@router.get("/brands/{brand_id}/citations", response_model=list[CitationRead])
def list_citations(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    engine: str | None = None,
    prompt_id: UUID | None = None,
):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    stmt = (
        select(Citation)
        .join(EngineRun, Citation.engine_run_id == EngineRun.id)
        .join(Prompt, EngineRun.prompt_id == Prompt.id)
        .where(Prompt.brand_id == b.id)
    )
    if engine:
        try:
            stmt = stmt.where(EngineRun.engine == EngineType(engine))
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid engine") from e
    if prompt_id:
        stmt = stmt.where(Prompt.id == prompt_id)
    stmt = stmt.order_by(Citation.created_at.desc()).limit(500)
    return list(db.scalars(stmt).all())


@router.get("/brands/{brand_id}/sov", response_model=SoVRead)
def get_sov(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    range: str = Query("30d", alias="range"),
):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    days = parse_range_days(range)
    s = compute_sov(db, tenant.id, b.id, days=days)
    return SoVRead(
        brand_id=b.id,
        range_days=days,
        brand_share=s.brand_share,
        competitor_share=s.competitor_share,
        third_party_share=s.third_party_share,
        neutral_share=s.neutral_share,
    )


@router.get("/brands/{brand_id}/sov/trend")
def get_sov_trend(brand_id: UUID, db: DbSession, tenant: CurrentTenant, days: int = Query(14, ge=1, le=90)):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    return {"brand_id": str(b.id), "series": trend_citations_per_day(db, tenant.id, b.id, days=days)}


@router.get("/brands/{brand_id}/sov/multi-engine")
def get_sov_multi_engine(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    range: str = Query("30d", alias="range"),
):
    """Share of voice by engine for the primary brand and each linked competitor (domain-matched citations)."""
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    days = parse_range_days(range)
    out = multientity_sov_by_engine(db, tenant.id, brand_id, days)
    if out.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Brand not found")
    return out


@router.get("/brands/{brand_id}/sov/entity-weekly-trend")
def get_sov_entity_weekly_trend(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    entity_id: UUID = Query(..., description="Primary brand id or a competitor brand id listed on the primary brand"),
    weeks: int = Query(12, ge=4, le=52),
):
    """Weekly citation share for one entity (your brand or a competitor) across all engines on this brand's prompts."""
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    out = entity_weekly_share_trend(db, tenant.id, brand_id, entity_id, weeks=weeks)
    err = out.get("error")
    if err == "not_found":
        raise HTTPException(status_code=404, detail="Brand not found")
    if err in ("invalid_entity",):
        raise HTTPException(status_code=400, detail="entity_id must be the primary brand or one of its competitors")
    return out


@router.get("/brands/{brand_id}/sov/multi-weekly-trend")
def get_sov_multi_weekly_trend(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    weeks: int = Query(12, ge=4, le=52),
):
    """Weekly SoV lines for the primary brand and each linked competitor (tracked citations only)."""
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    out = multi_entity_weekly_share_trend(db, tenant.id, brand_id, weeks=weeks)
    if out.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Brand not found")
    return out


@router.get("/brands/{brand_id}/gaps", response_model=list[GapRead])
def get_gaps(brand_id: UUID, db: DbSession, tenant: CurrentTenant):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    gaps = detect_gaps(db, tenant.id, b.id)
    return [GapRead(prompt_id=g.prompt_id, score=g.score, reason=g.reason) for g in gaps]


_OPPORTUNITY_STATUSES = frozenset({"open", "snoozed", "queued", "resolved"})


@router.get("/brands/{brand_id}/opportunities", response_model=list[OpportunityRead])
def list_brand_opportunities(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    status: str = Query("open", description="Filter: open | snoozed | queued | resolved"),
):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    if status not in _OPPORTUNITY_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status; use one of: {', '.join(sorted(_OPPORTUNITY_STATUSES))}",
        )
    rows = list_opportunities_for_brand(db, b.id, status=status)
    out: list[OpportunityRead] = []
    for o in rows:
        pr = db.get(Prompt, o.prompt_id)
        title = (pr.text if pr else "")[:512] or "(prompt)"
        scope_val = o.scope if (o.scope or "").strip() else None
        out.append(
            OpportunityRead(
                id=o.id,
                brand_id=o.brand_id,
                prompt_id=o.prompt_id,
                title=title,
                gap_type=o.gap_type,
                scope=scope_val,
                grade=o.grade,
                heat=heat_from_grade(o.grade),
                opportunity_score=float(o.opportunity_score),
                description=o.description,
                est_volume=o.est_volume,
                status=o.status,
                detected_at=o.detected_at,
            )
        )
    return out


@router.get("/opportunities/{opportunity_id}/detail", response_model=OpportunityDetailRead)
async def get_opportunity_detail_endpoint(
    opportunity_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
):
    o = db.get(Opportunity, opportunity_id)
    if not o:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    brand = db.get(Brand, o.brand_id)
    if not brand or brand.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    from citationpulse.services.opportunity_detail import get_opportunity_detail

    result = await get_opportunity_detail(db, opportunity_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    detail, source = result
    return OpportunityDetailRead(id=opportunity_id, detail=detail, source=source)


@router.get("/brands/{brand_id}/gaps-analysis", response_model=list[GapAnalysisRead])
def list_brand_gaps_analysis(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    from citationpulse.services.gap_analysis import list_gap_analysis_for_brand

    rows = list_gap_analysis_for_brand(db, brand_id)
    return [GapAnalysisRead.model_validate(row) for row in rows]


@router.get("/brands/{brand_id}/engine-mix")
def get_engine_mix(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    range: str = Query("30d", alias="range"),
):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    days = parse_range_days(range)
    return citation_counts_by_engine(db, tenant.id, brand_id, days)


@router.get("/brands/{brand_id}/matrix")
def get_brand_matrix(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    range: str = Query("30d", alias="range"),
):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    days = parse_range_days(range)
    payload = build_brand_matrix_payload(db, tenant.id, brand_id, days)
    if not payload:
        raise HTTPException(status_code=404, detail="Brand not found")
    return payload


@router.post("/alerts/rules", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
def create_alert_rule(body: AlertRuleCreate, db: DbSession, tenant: CurrentTenant):
    if body.brand_id:
        br = db.get(Brand, body.brand_id)
        if not br or br.tenant_id != tenant.id:
            raise HTTPException(status_code=404, detail="Brand not found")
    row = AlertRule(
        tenant_id=tenant.id,
        brand_id=body.brand_id,
        rule=body.rule,
        config=body.config,
        channel=body.channel,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/alerts/feed", response_model=list[AlertFeedItem])
def alerts_feed(db: DbSession, tenant: CurrentTenant, brand_id: UUID | None = None):
    stmt = select(Alert).join(Brand, Alert.brand_id == Brand.id).where(Brand.tenant_id == tenant.id)
    if brand_id:
        stmt = stmt.where(Alert.brand_id == brand_id)
    stmt = stmt.order_by(Alert.fired_at.desc()).limit(200)
    return list(db.scalars(stmt).all())
