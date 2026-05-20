from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from citationpulse.api.v1.billing import router as billing_router
from citationpulse.api.v1.competitors import router as competitors_router
from citationpulse.api.v1.endpoints import router as v1_router
from citationpulse.api.v1.scans import router as scans_router
from citationpulse.api.v1.operator import router as operator_router
from citationpulse.api.v1.partner import router as partner_router
from citationpulse.api.webhooks.stripe import router as stripe_router
import os

from citationpulse.core.config import celery_run_tasks_inline, get_settings
from citationpulse.core.observability import setup_observability
from citationpulse.db.runtime_bootstrap import ensure_opportunities_schema
from citationpulse.db.session import get_engine
from citationpulse.services.engine_routing import anthropic_configured, openai_configured
from citationpulse.services.llm_router import openrouter_configured
from citationpulse.services.scans_flow import available_engines

setup_observability()

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    s = get_settings()
    try:
        ensure_opportunities_schema(get_engine())
    except Exception:
        _log.exception(
            "startup schema bootstrap failed — check DATABASE_URL is linked to Postgres "
            "and uses postgresql+psycopg:// (Railway injects postgres://; we rewrite it)."
        )
    if s.environment.lower() == "production" and not openrouter_configured(s):
        _log.warning(
            "OPENROUTER_API_KEY is empty on this service — scans will fail OpenRouter auth until set."
        )
    yield


settings = get_settings()


def _normalise_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


origins = [_normalise_origin(o) for o in settings.api_cors_origins.split(",") if o.strip()]
railway_origin_regex = r"^https://([a-z0-9-]+\.)*up\.railway\.app$"
loopback_regex = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
rfc1918_http_regex = (
    r"^http://("
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}"
    r"):\d+$"
)
if settings.environment.lower() == "production":
    cors_origin_regex = f"{railway_origin_regex}|{loopback_regex}"
else:
    cors_origin_regex = f"{railway_origin_regex}|{loopback_regex}|{rfc1918_http_regex}"

app = FastAPI(title="CitationPulse API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    _log.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
def root():
    """Friendly index — visiting :8000/ in the browser used to show 404."""
    return {
        "name": "CitationPulse GEO API",
        "version": "0.1.0",
        "status": "ok",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "create_scan": "POST /api/v1/scans",
            "scan_snapshot": "GET /api/v1/scans/{scan_id}",
            "scan_report": "GET /api/v1/scans/{scan_id}/report",
            "scan_sov_multi_engine": "GET /api/v1/scans/{scan_id}/sov/multi-engine?range=84d",
            "scan_sov_multi_weekly": "GET /api/v1/scans/{scan_id}/sov/multi-weekly-trend?weeks=12",
            "scan_sov_summary": "GET /api/v1/scans/{scan_id}/sov/summary?range=84d&weeks=12",
            "scan_stream": "GET /api/v1/scans/{scan_id}/stream (SSE)",
            "public_share": "GET /api/v1/scans/public/{token}",
            "brand_opportunities": "GET /api/v1/brands/{brand_id}/opportunities?status=open",
            "competitor_analyze": "POST /api/v1/competitors/analyze",
        },
        "web_app": "http://localhost:3000",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "2026-05-19-claude-columns",
        "openrouter_configured": openrouter_configured(),
        "openai_configured": openai_configured(),
        "anthropic_configured": anthropic_configured(),
        "engines_available": available_engines(),
        "competitor_discovery_ready": openrouter_configured() or openai_configured(),
        "celery_tasks_inline": celery_run_tasks_inline(),
        "scan_parallel_executor": "threadpool",
        "git_commit": os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("RAILWAY_GIT_COMMIT")
        or None,
    }


@app.get("/metrics")
def metrics_stub():
    """Expose Prometheus metrics here (e.g. prometheus_client) in production."""
    return {"runs_per_minute": 0, "citations_captured": 0, "engine_error_rate": 0.0}


app.include_router(v1_router, prefix="/api/v1")
app.include_router(competitors_router, prefix="/api/v1")
app.include_router(scans_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(partner_router, prefix="/api/v1")
app.include_router(operator_router, prefix="/api/v1/operator")
app.include_router(stripe_router, prefix="/webhooks")

try:
    FastAPIInstrumentor.instrument_app(app)
except Exception:
    pass
