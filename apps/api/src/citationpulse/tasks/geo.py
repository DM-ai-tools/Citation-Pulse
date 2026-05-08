from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from citationpulse.adapters.registry import build_adapter
from citationpulse.celery_app import celery_app
from citationpulse.db.session import SessionLocal
from sqlalchemy import func, select

from citationpulse.models.domain import (
    Brand,
    Citation,
    EngineRun,
    EngineType,
    Prompt,
    RunStatus,
    Scan,
    default_engines,
)
from citationpulse.services.embeddings import embed_texts
from citationpulse.services.normalization import canonicalize_url, registrable_domain
from citationpulse.services.ownership import classify_domain
from citationpulse.services.sentiment import classify_snippet
from citationpulse.services.alerter import dispatch_partner_webhooks, fire_alert
from citationpulse.services.events import publish_scan_event
from citationpulse.services.scans_flow import (
    engine_progress_event,
    maybe_complete_scan,
    publish_cell_update,
)

_log = logging.getLogger(__name__)


@celery_app.task(name="citationpulse.run_engine", bind=True, max_retries=3)
def run_engine_task(self, run_id: str) -> str:
    db = SessionLocal()
    try:
        run = db.get(EngineRun, UUID(run_id))
        if not run:
            return "missing_run"
        prompt = db.get(Prompt, run.prompt_id)
        if not prompt:
            return "missing_prompt"
        brand = db.get(Brand, prompt.brand_id)
        if not brand:
            return "missing_brand"

        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        if run.scan_id:
            db.refresh(run)
            publish_cell_update(db, run)

        adapter = build_adapter(run.engine)
        ctx = {"run_id": run_id, "tenant_id": str(run.tenant_id), "brand_id": str(brand.id)}
        try:
            resp = asyncio.run(
                adapter.run(prompt.text, locale=prompt.locale, run_ctx=ctx),
            )
        except Exception as exc:  # noqa: BLE001
            run.status = RunStatus.ERROR.value
            run.error_message = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            if run.scan_id:
                db.refresh(run)
                publish_cell_update(db, run)
                maybe_complete_scan(db, run.scan_id)
            raise self.retry(exc=exc, countdown=60) from exc

        run.raw_ref = resp.raw_payload_ref
        run.cost_usd = resp.cost_usd
        for i, rc in enumerate(resp.citations):
            url = canonicalize_url(rc.url)
            db.add(
                Citation(
                    engine_run_id=run.id,
                    url=url,
                    domain=registrable_domain(url),
                    position=rc.position if rc.position is not None else i,
                    snippet=rc.snippet,
                    ownership="neutral",
                )
            )
        run.status = RunStatus.OK.value
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        if run.scan_id:
            eng = run.engine.value if hasattr(run.engine, "value") else str(run.engine)
            publish_scan_event(str(run.scan_id), engine_progress_event(db, run.scan_id, eng))
            maybe_complete_scan(db, run.scan_id)

        celery_app.send_task(
            "citationpulse.normalise",
            args=[run_id],
        )
        return "ok"
    finally:
        db.close()


@celery_app.task(name="citationpulse.normalise")
def normalise_task(run_id: str) -> str:
    db = SessionLocal()
    try:
        run = db.get(EngineRun, UUID(run_id))
        if not run:
            return "missing"
        prompt = db.get(Prompt, run.prompt_id)
        brand = db.get(Brand, prompt.brand_id) if prompt else None
        if not prompt or not brand:
            return "missing_prompt"
        cites = db.query(Citation).filter(Citation.engine_run_id == run.id).all()
        texts: list[str] = []
        for c in cites:
            url = canonicalize_url(c.url)
            c.url = url
            c.domain = registrable_domain(url)
            c.ownership = classify_domain(db, brand.tenant_id, url, brand.id)
            texts.append(c.snippet or c.url)
        vecs = embed_texts(texts) if texts else []
        for c, vec in zip(cites, vecs, strict=False):
            c.snippet_vec = vec
            c.sentiment = classify_snippet(c.snippet)
        db.commit()
        dispatch_partner_webhooks(
            db,
            brand.tenant_id,
            "citation.created",
            {"run_id": str(run.id), "urls": [c.url for c in cites]},
        )
        if run.scan_id:
            db.refresh(run)
            publish_cell_update(db, run)
            maybe_complete_scan(db, run.scan_id)
        celery_app.send_task("citationpulse.score", args=[str(brand.tenant_id), str(brand.id)])
        return "ok"
    finally:
        db.close()


@celery_app.task(name="citationpulse.score")
def score_task(tenant_id: str, brand_id: str) -> str:
    _log.info("score tenant=%s brand=%s", tenant_id, brand_id)
    return "ok"


@celery_app.task(name="citationpulse.nightly_alerts")
def nightly_alerts() -> str:
    db = SessionLocal()
    try:
        for brand in db.query(Brand).all():
            fire_alert(
                db,
                brand.id,
                "nightly_tick",
                {"brand": brand.name},
                "slack",
            )
        return "ok"
    finally:
        db.close()


@celery_app.task(name="citationpulse.canary")
def canary_check() -> str:
    from citationpulse.core.config import get_settings

    s = get_settings()
    if not s.canary_brand_id:
        return "skip"
    db = SessionLocal()
    try:
        brand = db.get(Brand, UUID(s.canary_brand_id))
        if not brand:
            return "missing_brand"
        enabled = {EngineType(v) for v in default_engines()}
        for eng in EngineType:
            if eng not in enabled:
                continue
            n = db.scalar(
                select(func.count())
                .select_from(Citation)
                .join(EngineRun, Citation.engine_run_id == EngineRun.id)
                .join(Prompt, EngineRun.prompt_id == Prompt.id)
                .where(Prompt.brand_id == brand.id, EngineRun.engine == eng)
            ) or 0
            if n == 0:
                fire_alert(db, brand.id, "canary_zero_citations", {"engine": eng.value}, "slack")
        return "ok"
    finally:
        db.close()


@celery_app.task(name="citationpulse.fan_out_scan")
def fan_out_scan_task(scan_id: str) -> str:
    db = SessionLocal()
    try:
        scan = db.get(Scan, UUID(scan_id))
        if not scan:
            return "missing_scan"
        brand = db.get(Brand, scan.brand_id)
        if not brand:
            return "missing_brand"
        prompts = db.query(Prompt).filter(Prompt.brand_id == brand.id, Prompt.enabled.is_(True)).all()
        eng_list = list(scan.engines) if scan.engines else default_engines()
        scan.status = "running"
        db.commit()
        n = max(1, len(prompts) * len(eng_list))
        publish_scan_event(scan_id, {"type": "scan.eta", "etaSeconds": min(900, n * 40)})

        for p in prompts:
            for e in eng_list:
                try:
                    eng = EngineType(e)
                except ValueError:
                    continue
                run = EngineRun(
                    tenant_id=brand.tenant_id,
                    prompt_id=p.id,
                    engine=eng,
                    status=RunStatus.QUEUED.value,
                    scan_id=scan.id,
                )
                db.add(run)
                db.flush()
                celery_app.send_task("citationpulse.run_engine", args=[str(run.id)])
        db.commit()
        return "enqueued"
    finally:
        db.close()


@celery_app.task(name="citationpulse.fan_out_brand")
def fan_out_brand(brand_id: str, engines: list[str] | None = None) -> str:
    db = SessionLocal()
    try:
        brand = db.get(Brand, UUID(brand_id))
        if not brand:
            return "missing"
        prompts = db.query(Prompt).filter(Prompt.brand_id == brand.id, Prompt.enabled.is_(True)).all()
        eng_list = engines or default_engines()
        for p in prompts:
            for e in eng_list:
                try:
                    eng = EngineType(e)
                except ValueError:
                    continue
                run = EngineRun(
                    tenant_id=brand.tenant_id,
                    prompt_id=p.id,
                    engine=eng,
                    status=RunStatus.QUEUED.value,
                )
                db.add(run)
                db.flush()
                celery_app.send_task("citationpulse.run_engine", args=[str(run.id)])
        db.commit()
        return "enqueued"
    finally:
        db.close()


@celery_app.task(name="citationpulse.daily_beat")
def daily_beat() -> str:
    db = SessionLocal()
    try:
        for b in db.query(Brand).all():
            fan_out_brand.delay(str(b.id))
        return "ok"
    finally:
        db.close()
