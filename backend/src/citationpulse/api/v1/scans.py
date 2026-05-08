from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from citationpulse.api.deps import DbSession
from citationpulse.celery_app import celery_app
from citationpulse.core.config import get_settings
from citationpulse.db.session import SessionLocal
from citationpulse.models.domain import Brand, EngineType, Prompt, Scan, ScanEvent
from citationpulse.schemas.scans import ScanCreate, ScanCreateResponse, ShareBody
from citationpulse.services.rate_limit import allow_anonymous_scan
from citationpulse.services.normalization import canonicalize_url, registrable_domain
from citationpulse.services.scans_flow import (
    available_engines,
    build_scan_report,
    build_scan_snapshot,
    get_or_create_anonymous_tenant,
)

router = APIRouter(prefix="/scans", tags=["scans"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _client_ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or (
        request.client.host if request.client else ""
    )


@router.post("", response_model=ScanCreateResponse, status_code=status.HTTP_201_CREATED)
def create_scan(request: Request, db: DbSession, body: ScanCreate) -> ScanCreateResponse:
    ip = _client_ip(request)
    if not allow_anonymous_scan(ip):
        raise HTTPException(status_code=429, detail="Too many scans from this IP — try again later")

    url = canonicalize_url(str(body.url))
    root = registrable_domain(url)
    if not root:
        raise HTTPException(status_code=400, detail="Could not parse domain from URL")

    tenant = get_or_create_anonymous_tenant(db)
    main = Brand(
        tenant_id=tenant.id,
        name=root,
        domains=[root],
        competitors=[],
    )
    db.add(main)
    db.flush()

    comp_ids: list[UUID] = []
    for raw in body.competitors:
        cu = canonicalize_url(raw if raw.startswith("http") else f"https://{raw}")
        dom = registrable_domain(cu)
        if not dom or dom == root:
            continue
        cb = Brand(tenant_id=tenant.id, name=dom, domains=[dom], competitors=[])
        db.add(cb)
        db.flush()
        comp_ids.append(cb.id)
    main.competitors = comp_ids
    db.flush()

    for text in body.prompts:
        db.add(
            Prompt(
                brand_id=main.id,
                text=text,
                locale=body.locale,
                enabled=True,
            )
        )

    requested = body.engines if body.engines else None
    eng_list = [e for e in (requested or []) if e in {x.value for x in EngineType}] or None
    eng_list = available_engines(eng_list)

    scan = Scan(
        tenant_id=tenant.id,
        brand_id=main.id,
        submitted_url=url,
        locale=body.locale,
        engines=eng_list,
        status="queued",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    celery_app.send_task("citationpulse.fan_out_scan", args=[str(scan.id)])
    return ScanCreateResponse(scan_id=str(scan.id))


def _get_scan(db: Session, scan_id: UUID) -> Scan:
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.get("/{scan_id}")
def get_scan(scan_id: UUID, db: DbSession):
    scan = _get_scan(db, scan_id)
    return build_scan_snapshot(db, scan)


@router.get("/{scan_id}/report")
def get_scan_report(scan_id: UUID, db: DbSession):
    scan = _get_scan(db, scan_id)
    return build_scan_report(db, scan)


@router.post("/{scan_id}/share")
def share_scan(scan_id: UUID, db: DbSession, body: ShareBody | None = None):
    import secrets

    scan = _get_scan(db, scan_id)
    public = True if body is None else body.share_public
    scan.share_public = public
    if public and not scan.share_token:
        scan.share_token = secrets.token_urlsafe(24)
    if not public:
        scan.share_token = None
    db.commit()
    db.refresh(scan)
    return {"share_token": scan.share_token, "share_public": scan.share_public}


@router.get("/public/{token}")
def get_public_scan(token: str, db: DbSession):
    scan = db.scalar(
        select(Scan).where(Scan.share_token == token, Scan.share_public.is_(True)),
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Report not found")
    return build_scan_report(db, scan)


async def _sse_gen(scan_id: UUID):
    """Stream `scan_events` rows for `scan_id` to the browser as SSE.

    Postgres-backed long-polling tail: each tick selects rows with `id > last_id`
    in arrival order. A keep-alive comment is emitted when there are no new rows
    so the connection doesn't get killed by intermediate proxies.
    """
    settings = get_settings()
    poll_s = max(0.1, float(settings.sse_poll_interval_s))
    keepalive_s = max(poll_s, float(settings.sse_keepalive_interval_s))

    last_id: int = 0
    last_keepalive_at: float = 0.0
    loop = asyncio.get_event_loop()

    def _fetch(after_id: int) -> list[tuple[int, dict]]:
        db = SessionLocal()
        try:
            rows = db.execute(
                select(ScanEvent.id, ScanEvent.payload)
                .where(ScanEvent.scan_id == scan_id, ScanEvent.id > after_id)
                .order_by(ScanEvent.id.asc())
                .limit(200)
            ).all()
            return [(int(r[0]), r[1]) for r in rows]
        finally:
            db.close()

    while True:
        try:
            rows = await asyncio.to_thread(_fetch, last_id)
        except Exception:  # noqa: BLE001
            await asyncio.sleep(poll_s)
            continue

        now = loop.time()
        if rows:
            for ev_id, payload in rows:
                last_id = ev_id
                yield f"data: {json.dumps(payload)}\n\n"
            last_keepalive_at = now
        elif now - last_keepalive_at >= keepalive_s:
            yield ": ping\n\n"
            last_keepalive_at = now

        await asyncio.sleep(poll_s)


@router.get("/{scan_id}/stream")
async def stream_scan(scan_id: UUID, db: DbSession):
    _get_scan(db, scan_id)
    return StreamingResponse(
        _sse_gen(scan_id),
        media_type="text/event-stream",
        headers=dict(SSE_HEADERS),
    )
