from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from citationpulse.core.config import (
    celery_run_tasks_inline,
    effective_celery_broker_url,
    effective_celery_result_backend,
    get_settings,
)

_settings = get_settings()

celery_app = Celery(
    "citationpulse",
    broker=effective_celery_broker_url(_settings),
    backend=effective_celery_result_backend(_settings),
)

# Local dev / Railway API-only: run tasks in the API process (BackgroundTasks + eager Celery).
# Production with a separate worker service: set CELERY_USE_WORKER=1 on API + worker.
_task_always_eager = celery_run_tasks_inline(_settings)

celery_app.conf.update(
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
    task_always_eager=_task_always_eager,
    task_eager_propagates=_task_always_eager,
    task_routes={
        "citationpulse.run_engine": {"queue": "default"},
        "citationpulse.normalise": {"queue": "default"},
        "citationpulse.score": {"queue": "default"},
        "citationpulse.nightly_alerts": {"queue": "default"},
        "citationpulse.canary": {"queue": "default"},
        "citationpulse.fan_out_brand": {"queue": "default"},
        "citationpulse.fan_out_scan": {"queue": "default"},
        "citationpulse.start_scan": {"queue": "default"},
        "citationpulse.run_scan_engine_waves": {"queue": "default"},
        "citationpulse.competitor_discovery_for_scan": {"queue": "default"},
        "citationpulse.enrich_competitor_after_scan": {"queue": "default"},
        "citationpulse.daily_beat": {"queue": "default"},
        "citationpulse.detect_opportunities": {"queue": "default"},
    },
    beat_schedule={
        "citationpulse-daily": {
            "task": "citationpulse.daily_beat",
            "schedule": crontab(hour=2, minute=0),
        },
        "citationpulse-detect-opportunities": {
            "task": "citationpulse.detect_opportunities",
            "schedule": crontab(hour=5, minute=0),
        },
        "citationpulse-nightly-alerts": {
            "task": "citationpulse.nightly_alerts",
            "schedule": crontab(hour=3, minute=15),
        },
        "citationpulse-canary": {
            "task": "citationpulse.canary",
            "schedule": crontab(hour=12, minute=0),
        },
    },
)

import citationpulse.tasks.geo  # noqa: E402, F401 — register tasks


@worker_process_init.connect
def _bootstrap_db_schema(**_kwargs: object) -> None:
    from citationpulse.db.runtime_bootstrap import ensure_opportunities_schema
    from citationpulse.db.session import get_engine

    ensure_opportunities_schema(get_engine())
