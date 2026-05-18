from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from citationpulse.api.deps import CurrentTenant, DbSession, get_auth_context
from citationpulse.tasks.geo import fan_out_brand
from citationpulse.models.domain import Alert, AlertRule, Brand, Citation, EngineRun, EngineType, Prompt
from citationpulse.schemas.brands import (
    AlertFeedItem,
    AlertRuleCreate,
    AlertRuleRead,
    BrandCreate,
    BrandRead,
    CitationRead,
    GapRead,
    OpportunityListResponse,
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
from citationpulse.services.opportunities import (
    count_opportunities_for_brand,
    demand_pill_from_bucket,
    heat_from_grade,
    list_opportunities_for_brand,
)
from citationpulse.services.rate_limit import allow_ad_hoc_run
from citationpulse.services.scorer import trend_citations_per_day
from citationpulse.services.sov import compute_sov

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


@router.get("/brands/{brand_id}/gaps", response_model=list[GapRead])
def get_gaps(brand_id: UUID, db: DbSession, tenant: CurrentTenant):
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    gaps = detect_gaps(db, tenant.id, b.id)
    return [GapRead(prompt_id=g.prompt_id, score=g.score, reason=g.reason) for g in gaps]


_OPPORTUNITY_STATUSES = frozenset({"open", "snoozed", "queued", "resolved"})
_OPPORTUNITY_GRADES = frozenset({"A", "B", "C"})
_OPPORTUNITY_GAP_TYPES = frozenset(
    {
        "absent_all",
        "competitor_dominant",
        "engine_specific_gap",
        "weak_engine",
        "refresh_content",
        "extend_presence",
    }
)


def _opportunity_to_read(db: Session, o, *, title_cache: dict[UUID, str] | None = None) -> OpportunityRead:
    """Hydrate one Opportunity row into the API response model.

    Pulls in the prompt text (cached per-request) and the Prompt's
    precomputed demand fields. Demand is read from ``prompts``, not from
    the Opportunity row, so the latest refresh is reflected immediately
    even if the nightly detect job hasn't re-run.
    """
    pr = None
    if title_cache is not None and o.prompt_id in title_cache:
        title = title_cache[o.prompt_id]
    else:
        pr = db.get(Prompt, o.prompt_id)
        title = (pr.text if pr else "")[:512] or "(prompt)"
        if title_cache is not None:
            title_cache[o.prompt_id] = title
    if pr is None:
        pr = db.get(Prompt, o.prompt_id)
    scope_val = o.scope if (o.scope or "").strip() else None
    bucket = getattr(pr, "demand_bucket", None) if pr else None
    return OpportunityRead(
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
        demand_score=float(pr.demand_score) if (pr and pr.demand_score is not None) else None,
        demand_bucket=bucket,
        demand_pill=demand_pill_from_bucket(bucket),
        demand_source=getattr(pr, "demand_source", None) if pr else None,
        demand_variant=getattr(pr, "demand_variant", None) if pr else None,
        demand_raw_volume=getattr(pr, "demand_raw_volume", None) if pr else None,
        demand_refreshed_at=getattr(pr, "demand_refreshed_at", None) if pr else None,
    )


@router.get("/brands/{brand_id}/opportunities")
def list_brand_opportunities(
    brand_id: UUID,
    db: DbSession,
    tenant: CurrentTenant,
    status: str = Query("open", description="Filter: open | snoozed | queued | resolved"),
    grade: str | None = Query(None, description="Filter: A | B | C (exact match)"),
    gap_type: str | None = Query(
        None,
        description=(
            "Filter by gap pattern. One of: absent_all | competitor_dominant "
            "| engine_specific_gap | weak_engine | refresh_content | extend_presence"
        ),
    ),
    limit: int = Query(100, ge=1, le=500, description="Page size (max 500)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    paginated: bool = Query(
        False,
        description="When true, response is {items, total, limit, offset, has_more}. Default is a flat list for back-compat.",
    ),
) -> list[OpportunityRead] | OpportunityListResponse:
    """List Top Gap Opportunities for a brand.

    Sort order (per spec):
        1. Grade A → B → C
        2. opportunity_score DESC
        3. detected_at DESC (tiebreaker)

    The endpoint is a **read-only view of precomputed rows** — it does NOT
    run the gap classifier or call DataForSEO. Schedule ``detect_opportunities``
    (nightly) and ``refresh_demand`` (weekly) to keep the table fresh.
    """
    b = db.get(Brand, brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    if status not in _OPPORTUNITY_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status; use one of: {', '.join(sorted(_OPPORTUNITY_STATUSES))}",
        )
    if grade is not None and grade.upper() not in _OPPORTUNITY_GRADES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid grade; use one of: {', '.join(sorted(_OPPORTUNITY_GRADES))}",
        )
    if gap_type is not None and gap_type not in _OPPORTUNITY_GAP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid gap_type; use one of: {', '.join(sorted(_OPPORTUNITY_GAP_TYPES))}",
        )

    rows = list_opportunities_for_brand(
        db,
        b.id,
        status=status,
        grade=grade,
        gap_type=gap_type,
        limit=limit,
        offset=offset,
    )
    title_cache: dict[UUID, str] = {}
    items = [_opportunity_to_read(db, o, title_cache=title_cache) for o in rows]

    if not paginated:
        return items

    total = count_opportunities_for_brand(
        db, b.id, status=status, grade=grade, gap_type=gap_type
    )
    return OpportunityListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < total,
    )


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
