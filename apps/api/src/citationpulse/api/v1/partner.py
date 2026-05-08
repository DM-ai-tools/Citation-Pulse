from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from citationpulse.api.deps import CurrentTenant, DbSession, get_auth_context
from citationpulse.models.domain import WebhookSubscription

router = APIRouter(dependencies=[Depends(get_auth_context)])


class WebhookSubCreate(BaseModel):
    url: str
    secret: str = Field(..., min_length=16)
    events: list[str] = Field(default_factory=lambda: ["citation.created", "alert.fired"])


@router.post("/webhooks/subscriptions", status_code=status.HTTP_201_CREATED)
def create_webhook(body: WebhookSubCreate, db: DbSession, tenant: CurrentTenant):
    row = WebhookSubscription(
        tenant_id=tenant.id,
        url=body.url,
        secret=body.secret,
        events=body.events,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "url": row.url, "events": row.events}


@router.get("/webhooks/subscriptions")
def list_webhooks(db: DbSession, tenant: CurrentTenant):
    rows = (
        db.query(WebhookSubscription)
        .filter(WebhookSubscription.tenant_id == tenant.id)
        .order_by(WebhookSubscription.created_at.desc())
        .all()
    )
    return [{"id": str(r.id), "url": r.url, "events": r.events, "active": r.active} for r in rows]


@router.delete("/webhooks/subscriptions/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(sub_id: UUID, db: DbSession, tenant: CurrentTenant) -> Response:
    row = db.get(WebhookSubscription, sub_id)
    if not row or row.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
