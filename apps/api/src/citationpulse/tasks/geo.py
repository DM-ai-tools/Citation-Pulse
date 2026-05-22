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
from citationpulse.services.engine_routing import engine_route, route_label
from citationpulse.services.direct_llm import DirectProviderError
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

# Parallel engine waves: wave 1 runs together, then wave 2 (reduces wall-clock vs one-by-one).
WAVE_1_ENGINES: frozenset[str] = frozenset(
    {EngineType.CHATGPT.value, EngineType.PERPLEXITY.value},
)
WAVE_2_ENGINES: frozenset[str] = frozenset(
    {EngineType.CLAUDE.value, EngineType.GEMINI.value},
)


def _engine_key(run: EngineRun) -> str:
    return run.engine.value if hasattr(run.engine, "value") else str(run.engine)


def wave_for_engine(engine_key: str) -> int:
    if engine_key in WAVE_1_ENGINES:
        return 1
    if engine_key in WAVE_2_ENGINES:
        return 2
    return 1


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


async def _run_single_engine_run_async(run_id: str) -> str:
    """Execute one engine run (own DB session — safe for asyncio.gather)."""
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

        engine_key = _engine_key(run)
        route = engine_route(engine_key)
        if route == "unconfigured":
            run.status = RunStatus.ERROR.value
            run.error_message = (
                f"No API key configured for {engine_key}. "
                "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, and/or OPENROUTER_API_KEY in the repo root .env."
            )[:4000]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            if run.scan_id:
                db.refresh(run)
                publish_cell_update(db, run)
                maybe_complete_scan(db, run.scan_id)
            return "error"

        adapter = build_adapter(run.engine)
        ctx = {"run_id": run_id, "tenant_id": str(run.tenant_id), "brand_id": str(brand.id)}
        try:
            resp = await adapter.run(prompt.text, locale=prompt.locale, run_ctx=ctx)
        except Exception as exc:  # noqa: BLE001
            run.status = RunStatus.ERROR.value
            msg = str(exc)
            if isinstance(exc, (LLMProviderError, DirectProviderError)) and exc.status_code == 401:
                label = route_label(route)
                provider = getattr(exc, "provider", None)
                if provider:
                    label = f"{provider} API (direct)"
                msg = f"{label} rejected the request (HTTP 401). Check API keys in .env. Details: {exc.body[:400]}"
            run.error_message = msg[:4000]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            if run.scan_id:
                db.refresh(run)
                publish_cell_update(db, run)
                maybe_complete_scan(db, run.scan_id)
            _log.warning("run_engine failed run_id=%s engine=%s: %s", run_id, run.engine, exc)
            return "error"

        if not (resp.raw_payload_ref or "").strip() and not resp.citations and not (resp.answer_text or "").strip():
            run.status = RunStatus.ERROR.value
            run.error_message = (
                f"{engine_key} returned no data ({route_label(route)}). "
                "Verify API keys in the repo root .env and restart the API."
            )[:4000]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            if run.scan_id:
                db.refresh(run)
                publish_cell_update(db, run)
                maybe_complete_scan(db, run.scan_id)
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
            eng = _engine_key(run)
            publish_scan_event(str(run.scan_id), engine_progress_event(db, run.scan_id, eng))
            publish_cell_update(db, run)
            maybe_complete_scan(db, run.scan_id)
        return "ok"
    finally:
        db.close()


@celery_app.task(name="citationpulse.run_engine")
def run_engine_task(run_id: str) -> str:
    """Single engine run (brand fan-out / retries). Scans use batched parallel waves."""
    return asyncio.run(_run_single_engine_run_async(run_id))


async def _run_engine_wave_async(run_ids: list[str], *, wave: int) -> None:
    if not run_ids:
        return
    _log.info("engine wave %s starting count=%s", wave, len(run_ids))
    results = await asyncio.gather(
        *[_run_single_engine_run_async(rid) for rid in run_ids],
        return_exceptions=True,
    )
    for rid, res in zip(run_ids, results, strict=True):
        if isinstance(res, Exception):
            _log.exception("parallel engine run raised run_id=%s wave=%s", rid, wave, exc_info=res)
    _log.info("engine wave %s finished count=%s", wave, len(run_ids))


async def _run_scan_engine_waves_async(wave1_ids: list[str], wave2_ids: list[str]) -> None:
    await _run_engine_wave_async(wave1_ids, wave=1)
    await _run_engine_wave_async(wave2_ids, wave=2)


@celery_app.task(name="citationpulse.run_scan_engine_waves")
def run_scan_engine_waves_task(
    scan_id: str,
    wave1_ids: list[str],
    wave2_ids: list[str],
) -> str:
    """Run scan engines in two parallel batches: ChatGPT+Perplexity, then Claude+Gemini."""
    try:
        asyncio.run(_run_scan_engine_waves_async(wave1_ids, wave2_ids))
        return f"ok:{len(wave1_ids)}+{len(wave2_ids)}"
    except Exception:
        _log.exception("run_scan_engine_waves failed scan_id=%s", scan_id)
        return "error"


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


@celery_app.task(name="citationpulse.start_scan")
def start_scan_task(scan_id: str) -> str:
    """Fan out engine citation checks immediately; competitor landscape runs in parallel."""
    db = SessionLocal()
    try:
        from citationpulse.services.competitor_discovery_scan import (
            auto_discover_enabled,
            set_discovery_status,
        )

        scan = db.get(Scan, UUID(scan_id))
        if not scan:
            return "missing_scan"

        # Engine runs first so the live scan matrix progresses immediately.
        fan_out_scan_task(scan_id)

        if auto_discover_enabled(scan) and not scan.competitor_discovery:
            set_discovery_status(scan, "pending")
            scan.status = "running"
            db.commit()
            try:
                publish_scan_event(scan_id, {"type": "competitor.discovery.started"})
            except Exception:
                _log.debug("competitor.discovery.started event failed scan_id=%s", scan_id)
            try:
                competitor_discovery_for_scan_task.delay(scan_id)
            except Exception:
                _log.exception("enqueue competitor_discovery failed scan_id=%s", scan_id)
                set_discovery_status(scan, "failed")
                db.commit()

        return "ok"
    except Exception:
        _log.exception("start_scan_task failed scan_id=%s", scan_id)
        try:
            fan_out_scan_task(scan_id)
        except Exception:
            _log.exception("fan_out fallback after start_scan failed scan_id=%s", scan_id)
        return "error"
    finally:
        db.close()


@celery_app.task(name="citationpulse.enrich_competitor_after_scan")
def enrich_competitor_after_scan_task(scan_id: str) -> str:
    """Post-scan competitor expansion (must not run inside engine ``asyncio.run``)."""
    db = SessionLocal()
    try:
        from citationpulse.services.competitor_pipeline import (
            enrich_competitor_discovery_after_scan_complete,
        )

        enrich_competitor_discovery_after_scan_complete(db, UUID(scan_id))
        try:
            publish_scan_event(scan_id, {"type": "competitor.discovery.ready"})
        except Exception:
            _log.debug("competitor.discovery.ready after enrich failed scan_id=%s", scan_id)
        return "ok"
    except Exception:
        _log.exception("enrich_competitor_after_scan failed scan_id=%s", scan_id)
        return "error"
    finally:
        db.close()


@celery_app.task(name="citationpulse.competitor_discovery_for_scan")
def competitor_discovery_for_scan_task(scan_id: str) -> str:
    """Re-run tiered competitor discovery (manual/backfill). Normal scans use ``start_scan_task``."""
    db = SessionLocal()
    try:
        from citationpulse.services.competitor_discovery_scan import (
            run_competitor_discovery_for_scan,
            set_discovery_status,
        )

        scan = db.get(Scan, UUID(scan_id))
        if not scan:
            return "missing_scan"
        result = run_competitor_discovery_for_scan(db, scan)
        if not result and not scan.competitor_discovery:
            params = scan.discovery_params if isinstance(scan.discovery_params, dict) else {}
            # Do not overwrite explicit failures from analyze_competitors validation.
            if params.get("discovery_status") == "pending":
                set_discovery_status(scan, "failed")
        if result is not None or scan.competitor_discovery:
            from citationpulse.services.competitor_citation_visibility import reclassify_scan_citations

            reclassify_scan_citations(db, scan)
        db.commit()
        if result is not None:
            try:
                publish_scan_event(scan_id, {"type": "competitor.discovery.ready"})
            except Exception:
                _log.debug("competitor.discovery.ready event failed scan_id=%s", scan_id)
        return "ok"
    except Exception:
        _log.exception("competitor_discovery_for_scan_task failed scan_id=%s", scan_id)
        return "error"
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
        wave_count = 2 if any(e in WAVE_2_ENGINES for e in eng_list) else 1
        publish_scan_event(
            scan_id,
            {"type": "scan.eta", "etaSeconds": min(900, max(1, len(prompts)) * wave_count * 35)},
        )

        wave1_ids: list[str] = []
        wave2_ids: list[str] = []
        runs_enqueued = 0
        for p in prompts:
            for e in eng_list:
                try:
                    eng = EngineType(e)
                except ValueError:
                    continue
                eng_key = eng.value
                run = EngineRun(
                    tenant_id=brand.tenant_id,
                    prompt_id=p.id,
                    engine=eng,
                    status=RunStatus.QUEUED.value,
                    scan_id=scan.id,
                )
                db.add(run)
                db.flush()
                rid = str(run.id)
                if wave_for_engine(eng_key) == 1:
                    wave1_ids.append(rid)
                else:
                    wave2_ids.append(rid)
                runs_enqueued += 1
        db.commit()
        if runs_enqueued > 0:
            run_scan_engine_waves_task.delay(scan_id, wave1_ids, wave2_ids)

        if runs_enqueued == 0:
            # No `EngineRun` rows → `maybe_complete_scan` can never finish (expected > 0, total == 0).
            scan = db.get(Scan, UUID(scan_id))
            if scan:
                scan.status = "completed"
                scan.completed_at = datetime.now(timezone.utc)
                scan.score_overall = 0
                db.commit()
                publish_scan_event(scan_id, {"type": "scan.completed", "score": 0})
            _log.warning("fan_out_scan produced zero runs scan_id=%s prompts=%s engines=%s", scan_id, len(prompts), eng_list)
            return "no_runs"

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
    """Nightly (or on-demand): classify gaps, score, upsert `opportunities` rows per brand."""
    from citationpulse.services.opportunities import detect_opportunities_for_brand, sync_prompt_volumes_for_brand

    db = SessionLocal()
    try:
        if brand_id:
            sync_prompt_volumes_for_brand(db, UUID(brand_id))
            detect_opportunities_for_brand(db, UUID(brand_id))
            return "ok"
        brands = list(db.query(Brand).all())
        for b in brands:
            sync_prompt_volumes_for_brand(db, b.id)
            detect_opportunities_for_brand(db, b.id)
        return f"ok:{len(brands)}"
    finally:
        db.close()

