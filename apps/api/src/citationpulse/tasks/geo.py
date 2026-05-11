from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from citationpulse.adapters.base import EngineResponse
from citationpulse.adapters.registry import build_adapter
from citationpulse.celery_app import celery_app
from citationpulse.db.session import SessionLocal
from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
from citationpulse.services.llm_router import LLMProviderError
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


def _persist_citations_from_response(db: Session, run: EngineRun, resp: EngineResponse) -> int:
    """Insert citation rows from the adapter response; skip invalid / duplicate URLs."""
    seen: set[str] = set()
    pos = 0
    n = 0
    for rc in resp.citations:
        raw = (rc.url or "").strip()
        if not raw:
            continue
        url = canonicalize_url(raw)
        dom = registrable_domain(url)
        if not dom:
            continue
        if url in seen:
            continue
        seen.add(url)
        db.add(
            Citation(
                engine_run_id=run.id,
                url=url,
                domain=dom,
                position=rc.position if rc.position is not None else pos,
                snippet=rc.snippet,
                ownership="neutral",
            )
        )
        pos += 1
        n += 1
    return n


@celery_app.task(name="citationpulse.score")
def score_task(tenant_id: str, brand_id: str) -> str:
    _log.info("score tenant=%s brand=%s", tenant_id, brand_id)
    return "ok"


def normalise_citations_for_run(db: Session, run: EngineRun) -> bool:
    """Classify domains, embeddings, sentiment; commit. Does not emit SSE or complete scans.

    Returns False if prompt/brand are missing.
    """
    prompt = db.get(Prompt, run.prompt_id)
    brand = db.get(Brand, prompt.brand_id) if prompt else None
    if not prompt or not brand:
        return False
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
    try:
        dispatch_partner_webhooks(
            db,
            brand.tenant_id,
            "citation.created",
            {"run_id": str(run.id), "urls": [c.url for c in cites]},
        )
    except Exception as exc:
        _log.warning("dispatch_partner_webhooks failed run_id=%s: %s", run.id, exc)
    try:
        score_task.delay(str(brand.tenant_id), str(brand.id))
    except Exception as exc:
        _log.warning("score_task enqueue failed: %s", exc)
    return True


@celery_app.task(name="citationpulse.run_engine")
def run_engine_task(run_id: str) -> str:
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
            msg = str(exc)
            if isinstance(exc, LLMProviderError) and exc.status_code == 401:
                msg = (
                    "OpenRouter rejected the request (HTTP 401). "
                    "Set OPENROUTER_API_KEY on Railway for this service (same value as local .env). "
                    f"Details: {exc.body[:400]}"
                )
            run.error_message = msg[:4000]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            if run.scan_id:
                db.refresh(run)
                publish_cell_update(db, run)
                maybe_complete_scan(db, run.scan_id)
            # Do not Celery-retry here: eager mode runs inside Starlette BackgroundTasks and
            # `raise self.retry` surfaces as "Exception in ASGI application" after POST /scans.
            _log.warning("run_engine failed run_id=%s engine=%s: %s", run_id, run.engine, exc)
            return "error"

        run.raw_ref = resp.raw_payload_ref
        run.cost_usd = resp.cost_usd
        n_cites = _persist_citations_from_response(db, run, resp)
        if not n_cites and (resp.answer_text or "").strip():
            _log.debug(
                "engine_run=%s engine=%s: zero citations after normalize; answer_len=%s",
                run_id,
                run.engine,
                len(resp.answer_text or ""),
            )
        run.status = RunStatus.OK.value
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        try:
            if not normalise_citations_for_run(db, run):
                normalise_task.delay(run_id)
        except Exception:
            _log.exception("inline normalise failed run_id=%s; falling back to async task", run_id)
            normalise_task.delay(run_id)
        db.refresh(run)
        if run.scan_id:
            eng = run.engine.value if hasattr(run.engine, "value") else str(run.engine)
            publish_scan_event(str(run.scan_id), engine_progress_event(db, run.scan_id, eng))
            publish_cell_update(db, run)
            maybe_complete_scan(db, run.scan_id)
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
        if not normalise_citations_for_run(db, run):
            return "missing_prompt"
        db.refresh(run)
        if run.scan_id:
            publish_cell_update(db, run)
            maybe_complete_scan(db, run.scan_id)
        return "ok"
    finally:
        db.close()


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
                db.commit()
                # Must commit before enqueue: run_engine uses its own session and cannot see
                # uncommitted rows; eager mode runs immediately (no time for a final batch commit).
                run_engine_task.delay(str(run.id))
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
                db.commit()
                run_engine_task.delay(str(run.id))
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
