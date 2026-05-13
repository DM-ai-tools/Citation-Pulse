from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from citationpulse.api.deps import CurrentTenant, DbSession, get_auth_context
from citationpulse.core.config import get_settings
from citationpulse.models.domain import Brand, CampaignTask, CommsLog
from citationpulse.services.dataforseo_keywords import (
    DataForSEOError,
    dataforseo_configured,
    fetch_google_ads_search_volumes,
)

router = APIRouter(dependencies=[Depends(get_auth_context)])


class CampaignCreate(BaseModel):
    brand_id: UUID
    prompt_id: UUID | None = None
    notes: str | None = None


class CommsCreate(BaseModel):
    brand_id: UUID
    entry: str = Field(..., min_length=1)


class KeywordVolumeBody(BaseModel):
    """Google Ads monthly search volume estimates for the given geo.

    Returns last-12-months average ``search_volume`` plus a ``search_volume_trend``
    array with per-month breakdown (year, month, search_volume).
    Filter the trend client-side for a specific month.
    """

    keywords: list[str] = Field(..., min_length=1, max_length=1000)
    location_code: int = Field(
        ...,
        description="DataForSEO location_code (geo). E.g. 2840 US, 2036 Australia.",
    )
    language_code: str = Field(default="en", min_length=2, max_length=8)


@router.post("/campaigns", status_code=status.HTTP_201_CREATED)
def queue_campaign(body: CampaignCreate, db: DbSession, tenant: CurrentTenant):
    b = db.get(Brand, body.brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    row = CampaignTask(
        tenant_id=tenant.id,
        brand_id=body.brand_id,
        prompt_id=body.prompt_id,
        notes=body.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "status": row.status}


@router.get("/campaigns")
def list_campaigns(db: DbSession, tenant: CurrentTenant):
    rows = db.query(CampaignTask).filter(CampaignTask.tenant_id == tenant.id).order_by(CampaignTask.created_at.desc()).limit(200).all()
    return [{"id": str(r.id), "brand_id": str(r.brand_id), "status": r.status, "notes": r.notes} for r in rows]


@router.post("/comms", status_code=status.HTTP_201_CREATED)
def log_comms(body: CommsCreate, db: DbSession, tenant: CurrentTenant):
    b = db.get(Brand, body.brand_id)
    if not b or b.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    row = CommsLog(tenant_id=tenant.id, brand_id=body.brand_id, entry=body.entry)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id)}


@router.get("/comms")
def list_comms(db: DbSession, tenant: CurrentTenant, brand_id: UUID | None = None):
    q = db.query(CommsLog).filter(CommsLog.tenant_id == tenant.id)
    if brand_id:
        q = q.filter(CommsLog.brand_id == brand_id)
    rows = q.order_by(CommsLog.created_at.desc()).limit(200).all()
    return [{"id": str(r.id), "brand_id": str(r.brand_id), "entry": r.entry, "at": r.created_at.isoformat()} for r in rows]


@router.post("/keywords/search-volume")
def keyword_search_volume(body: KeywordVolumeBody, tenant: CurrentTenant):
    """Proxy to DataForSEO Google Ads search volume (monthly estimates) for GEO + language.

    Returns ``items`` — one object per keyword with:
      - ``keyword``          — the queried keyword
      - ``search_volume``    — avg monthly searches across last 12 months
      - ``competition``      — 0-1 advertiser competition score
      - ``cpc``              — average cost per click USD
      - ``monthly_searches`` — list of 12 x {year, month, search_volume} objects

    To get a specific month: filter ``monthly_searches`` by year+month client-side.

    Requires ``DATAFORSEO_LOGIN`` and ``DATAFORSEO_PASSWORD`` in API .env,
    followed by an **API restart** (uvicorn caches settings at startup).
    """
    _ = tenant
    try:
        rows = fetch_google_ads_search_volumes(
            body.keywords,
            location_code=body.location_code,
            language_code=body.language_code,
        )
    except DataForSEOError as exc:
        http_status = exc.status_code or status.HTTP_502_BAD_GATEWAY
        detail = str(exc)
        if exc.raw:
            detail += f" | raw: {exc.raw}"
        raise HTTPException(status_code=http_status, detail=detail) from exc

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "DataForSEO returned 0 rows. "
                "Check: (1) credentials correct, (2) API restarted after .env update, "
                "(3) location_code is valid, (4) keywords are in the chosen language/market."
            ),
        )
    return {"items": rows, "count": len(rows)}
