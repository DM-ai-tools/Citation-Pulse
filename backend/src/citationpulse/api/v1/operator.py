from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from citationpulse.api.deps import CurrentTenant, DbSession, get_auth_context
from citationpulse.models.domain import Brand, CampaignTask, CommsLog

router = APIRouter(dependencies=[Depends(get_auth_context)])


class CampaignCreate(BaseModel):
    brand_id: UUID
    prompt_id: UUID | None = None
    notes: str | None = None


class CommsCreate(BaseModel):
    brand_id: UUID
    entry: str = Field(..., min_length=1)


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
