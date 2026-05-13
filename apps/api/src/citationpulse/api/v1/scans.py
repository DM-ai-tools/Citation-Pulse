from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from citationpulse.api.deps import DbSession
from citationpulse.core.config import get_settings
from citationpulse.db.session import SessionLocal
from citationpulse.models.domain import Brand, EngineType, Prompt, Scan, ScanEvent, all_engines
from citationpulse.schemas.scans import ScanCreate, ScanCreateResponse, ShareBody
from citationpulse.services.client_ip import effective_client_ip, is_mesh_or_unresolved_client_ip
from citationpulse.services.rate_limit import allow_anonymous_scan
from citationpulse.services.normalization import canonicalize_url, registrable_domain
from citationpulse.services.brand_dashboard import parse_range_days
from citationpulse.services.scans_flow import (
    available_engines,
    build_scan_report,
    build_scan_snapshot,
    get_or_create_anonymous_tenant,
)
from citationpulse.services.sov_entities import (
    multi_entity_weekly_share_trend,
    multientity_sov_by_engine,
)
from citationpulse.tasks.geo import fan_out_scan_task

router = APIRouter(prefix="/scans", tags=["scans"])
_log = logging.getLogger(__name__)


def _enqueue_fan_out_scan(scan_id: str) -> None:
    try:
        fan_out_scan_task.delay(scan_id)
    except Exception:
        _log.exception("fan_out_scan failed scan_id=%s", scan_id)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("", response_model=ScanCreateResponse, status_code=status.HTTP_201_CREATED)
def create_scan(
    request: Request,
    db: DbSession,
    background_tasks: BackgroundTasks,
    body: ScanCreate,
) -> ScanCreateResponse:
    settings = get_settings()
    ip = effective_client_ip(request)
    rl_key = ip
    rl_limit = settings.anonymous_scan_rate_limit_per_hour
    if is_mesh_or_unresolved_client_ip(ip):
        # Avoid bucketing the whole world behind Railway's 100.64 mesh into 8–24 req/hour.
        rl_key = "__platform_mesh__"
        rl_limit = settings.anonymous_scan_mesh_rate_limit_per_hour
    if not allow_anonymous_scan(rl_key, limit_per_hour=rl_limit):
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

    # Defer so the client gets 201 immediately; with task_always_eager (default in dev) the
    # full fan-out + engine runs still execute in this process after the response is sent.
    background_tasks.add_task(_enqueue_fan_out_scan, str(scan.id))
    return ScanCreateResponse(scan_id=str(scan.id))


def _get_scan(db: Session, scan_id: UUID) -> Scan:
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


def _empty_multi_from_brand(db: Session, brand: Brand, tenant_id: UUID, days: int) -> dict[str, object]:
    """Valid SoV multi payload when the real query fails so the funnel report can still render."""
    primary = brand
    competitors: dict[UUID, Brand] = {}
    for cid in primary.competitors or []:
        c = db.get(Brand, cid)
        if c and c.tenant_id == tenant_id:
            competitors[cid] = c
    engines = all_engines()
    zero_shares = {e: 0.0 for e in engines}
    entity_rows: list[dict[str, object]] = [
        {"entity_id": str(primary.id), "name": primary.name, "role": "brand", "shares_by_engine": dict(zero_shares)},
    ]
    for cid, comp in competitors.items():
        entity_rows.append(
            {"entity_id": str(cid), "name": comp.name, "role": "competitor", "shares_by_engine": dict(zero_shares)},
        )
    return {
        "primary_brand_id": str(primary.id),
        "range_days": days,
        "engines": engines,
        "entities": entity_rows,
        "totals": {"brand_citations": 0, "competitor_citations": 0},
    }


def _empty_weekly_from_multi(multi: dict[str, object], weeks: int) -> dict[str, object]:
    ents_raw = multi.get("entities") or []
    entities_meta: list[dict[str, str]] = []
    for e in ents_raw:
        if not isinstance(e, dict) or "entity_id" not in e:
            continue
        entities_meta.append(
            {
                "entity_id": str(e["entity_id"]),
                "name": str(e.get("name", "")),
                "role": str(e.get("role", "other")),
            }
        )
    primary_id = str(multi.get("primary_brand_id") or (entities_meta[0]["entity_id"] if entities_meta else ""))
    return {"primary_brand_id": primary_id, "weeks": weeks, "entities": entities_meta, "series": []}


@router.get("/{scan_id}/report")
def get_scan_report(scan_id: UUID, db: DbSession):
    scan = _get_scan(db, scan_id)
    return build_scan_report(db, scan)


@router.get("/{scan_id}/sov/multi-engine")
def get_scan_sov_multi_engine(
    scan_id: UUID,
    db: DbSession,
    response: Response,
    range: str = Query("30d", alias="range"),
):
    """Multi-entity SoV by engine for this scan's brand (public; same access model as ``/report``).

    Funnel report pages must not call ``GET /brands/.../sov/*`` (Clerk + tenant checks); use this
    route keyed by ``scan_id`` instead.
    """
    response.headers["Cache-Control"] = "no-store"
    scan = _get_scan(db, scan_id)
    brand = db.get(Brand, scan.brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Scan has no brand")
    days = parse_range_days(range)
    return multientity_sov_by_engine(db, brand.tenant_id, brand.id, days)


@router.get("/{scan_id}/sov/multi-weekly-trend")
def get_scan_sov_multi_weekly_trend(
    scan_id: UUID,
    db: DbSession,
    response: Response,
    weeks: int = Query(12, ge=4, le=52),
):
    """Weekly multi-entity SoV for this scan's brand (public; same access model as ``/report``)."""
    response.headers["Cache-Control"] = "no-store"
    scan = _get_scan(db, scan_id)
    brand = db.get(Brand, scan.brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Scan has no brand")
    return multi_entity_weekly_share_trend(db, brand.tenant_id, brand.id, weeks=weeks)


@router.get("/{scan_id}/sov/summary")
def get_scan_sov_summary(
    scan_id: UUID,
    db: DbSession,
    response: Response,
    range: str = Query("84d", alias="range"),
    weeks: int = Query(12, ge=4, le=52),
):
    """Return multi-engine + weekly SoV in one response (public; same access as ``/report``).

    Funnel report pages use this instead of two parallel fetches so a single failing leg
    does not surface as a hard error when the other succeeds.
    """
    response.headers["Cache-Control"] = "no-store"
    scan = _get_scan(db, scan_id)
    brand = db.get(Brand, scan.brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Scan has no brand")
    days = parse_range_days(range)

    try:
        cand = multientity_sov_by_engine(db, brand.tenant_id, brand.id, days)
        if isinstance(cand, dict) and cand.get("error"):
            multi = _empty_multi_from_brand(db, brand, brand.tenant_id, days)
        else:
            multi = cand
    except Exception:
        _log.exception("multientity_sov_by_engine failed scan_id=%s", scan_id)
        multi = _empty_multi_from_brand(db, brand, brand.tenant_id, days)

    try:
        cand_w = multi_entity_weekly_share_trend(db, brand.tenant_id, brand.id, weeks=weeks)
        if isinstance(cand_w, dict) and cand_w.get("error"):
            weekly = _empty_weekly_from_multi(multi, weeks)
        else:
            weekly = cand_w
    except Exception:
        _log.exception("multi_entity_weekly_share_trend failed scan_id=%s", scan_id)
        weekly = _empty_weekly_from_multi(multi, weeks)

    return {"multi_engine": multi, "multi_weekly_trend": weekly}


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


@router.get("/{scan_id}")
def get_scan(scan_id: UUID, db: DbSession):
    """Scan snapshot — registered **after** all ``/{scan_id}/…`` routes so ``/sov/…`` paths are not shadowed."""
    scan = _get_scan(db, scan_id)
    return build_scan_snapshot(db, scan)
