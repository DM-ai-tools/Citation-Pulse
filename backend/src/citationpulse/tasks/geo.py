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
from citationpulse.core.config import get_settings
from citationpulse.services.engine_routing import engine_route, route_label
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


def _provider_error_message(exc: Exception, engine_key: str) -> str:
    route = engine_route(engine_key)
    label = route_label(route)
    if isinstance(exc, LLMProviderError) and exc.status_code == 401:
        if route == "openai_direct":
            return (
                "OpenAI rejected the request (HTTP 401). Set OPENAI_API_KEY in .env. "
                f"Details: {exc.body[:400]}"
            )
        if route == "anthropic_direct":
            return (
                "Anthropic rejected the request (HTTP 401). Set ANTHROPIC_API_KEY in .env. "
                f"Details: {exc.body[:400]}"
            )
        return (
            "OpenRouter rejected the request (HTTP 401). Set OPENROUTER_API_KEY for Gemini/Perplexity. "
            f"Details: {exc.body[:400]}"
        )
    return f"{label}: {exc}"[:4000]


def _execute_engine_run(run_id: str) -> str:
    """Run one engine job (sync). Used by single-run and parallel batch tasks."""
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

        engine_key = run.engine.value if hasattr(run.engine, "value") else str(run.engine)
        if engine_route(engine_key) == "unconfigured":
            run.status = RunStatus.ERROR.value
            run.error_message = (
                f"No API key configured for {engine_key} "
                f"(route: {route_label('unconfigured')}). "
                "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, and/or OPENROUTER_API_KEY."
            )[:4000]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            if run.scan_id:
                db.refresh(run)
                publish_cell_update(db, run)
                maybe_complete_scan(db, run.scan_id)
            return "error"

        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        if run.scan_id:
            db.refresh(run)
            publish_cell_update(db, run)

        adapter = build_adapter(run.engine)
        ctx = {"run_id": run_id, "tenant_id": str(run.tenant_id), "brand_id": str(brand.id)}
        try:
            resp = asyncio.run(adapter.run(prompt.text, locale=prompt.locale, run_ctx=ctx))
        except Exception as exc:  # noqa: BLE001
            run.status = RunStatus.ERROR.value
            run.error_message = _provider_error_message(exc, engine_key)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            if run.scan_id:
                db.refresh(run)
                publish_cell_update(db, run)
                maybe_complete_scan(db, run.scan_id)
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


@celery_app.task(name="citationpulse.run_engine")
def run_engine_task(run_id: str) -> str:
    return _execute_engine_run(run_id)


@celery_app.task(name="citationpulse.run_engines_parallel")
def run_engines_parallel_task(run_ids: list[str]) -> str:
    """Execute all engine runs for a scan concurrently (asyncio + thread pool)."""
    if not run_ids:
        return "empty"
    settings = get_settings()
    limit = max(1, settings.scan_parallel_max_concurrent)
    sem = asyncio.Semaphore(limit)

    async def _one(rid: str) -> str:
        async with sem:
            return await asyncio.to_thread(_execute_engine_run, rid)

    async def _run_all():
        # gather() must run inside asyncio.run()'s loop — calling gather() as asyncio.run()'s
        # argument runs it in the AnyIO worker thread with no loop (uvicorn + uvloop).
        return await asyncio.gather(*(_one(rid) for rid in run_ids), return_exceptions=True)

    results = asyncio.run(_run_all())
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        _log.warning("run_engines_parallel had %s errors", len(errors))
    return "ok"


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
        run_ids: list[str] = []
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
                run_ids.append(str(run.id))

        if not run_ids:
            return "no_runs"
        settings = get_settings()
        parallel = settings.scan_parallel_engines and len(run_ids) > 1
        n = len(run_ids)
        if parallel:
            eta_factor = max(1, (n + settings.scan_parallel_max_concurrent - 1) // settings.scan_parallel_max_concurrent)
            eta_seconds = min(900, 20 + eta_factor * 25)
        else:
            eta_seconds = min(900, n * 40)
        publish_scan_event(scan_id, {"type": "scan.eta", "etaSeconds": eta_seconds})
        if parallel:
            run_engines_parallel_task.delay(run_ids)
        else:
            for rid in run_ids:
                run_engine_task.delay(rid)
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


@celery_app.task(name="citationpulse.detect_opportunities")
def detect_opportunities_task(brand_id: str | None = None) -> str:
    """Nightly Top Gap Opportunities detection.

    Runs AFTER normalise + score_cells in the pipeline:
        normalise → score_cells → detect_opportunities

    The task is idempotent: it upserts opportunity rows keyed by
    (brand_id, prompt_id, gap_type, scope) and marks rows that no longer
    match any gap pattern as ``status='resolved'`` (audit trail preserved).
    """
    from citationpulse.services.opportunities import detect_opportunities_for_brand

    db = SessionLocal()
    try:
        if brand_id:
            detect_opportunities_for_brand(db, UUID(brand_id))
            return "ok"
        brands = list(db.query(Brand).all())
        for b in brands:
            detect_opportunities_for_brand(db, b.id)
        return f"ok:{len(brands)}"
    finally:
        db.close()


@celery_app.task(name="citationpulse.refresh_demand", bind=True, max_retries=2)
def refresh_demand_task(
    self,  # type: ignore[no-untyped-def]
    brand_id: str | None = None,
    max_age_days: int = 7,
    batch_size: int = 200,
) -> str:
    """Weekly demand refresh — runs the 4-step fallback for prompts >7d old.

    DataForSEO lookups are cached in Redis for 7 days (per (variant, locale)),
    so re-runs within the same week are cheap even at scale.

    Arguments:
        brand_id:     optional UUID to scope the refresh to a single brand.
        max_age_days: how old ``demand_refreshed_at`` has to be before we
                      consider the prompt stale. Default = 7d matches the
                      Redis TTL on DataForSEO lookups.
        batch_size:   how many prompts to process per commit. Lower this if
                      worker memory becomes an issue on huge tenants.
    """
    from citationpulse.services.demand import (
        refresh_demand_for_prompts,
        stale_prompt_ids,
    )
    from citationpulse.models.domain import Prompt as PromptModel
    from sqlalchemy import select

    db = SessionLocal()
    try:
        if brand_id:
            stmt = select(PromptModel.id).where(
                PromptModel.brand_id == UUID(brand_id),
                PromptModel.enabled.is_(True),
            )
            ids = list(db.scalars(stmt).all())
        else:
            ids = stale_prompt_ids(db, max_age_days=int(max_age_days))

        total = 0
        for i in range(0, len(ids), int(batch_size)):
            chunk = ids[i : i + int(batch_size)]
            total += refresh_demand_for_prompts(db, chunk)
        return f"ok:{total}"
    except Exception as exc:  # noqa: BLE001
        _log.warning("refresh_demand failed: %s; retry=%s", exc, self.request.retries)
        try:
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        except Exception:
            return "error"
    finally:
        db.close()
