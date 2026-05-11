from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from citationpulse.core.config import (
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

_use_worker = os.environ.get("CELERY_USE_WORKER", "").lower() in ("1", "true", "yes")
_eager_env = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").strip().lower()
_dev = _settings.environment.lower() in ("development", "dev", "local")
_task_always_eager = _eager_env in ("1", "true", "yes") or (
    _dev and not _use_worker and _eager_env not in ("0", "false", "no")
)

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
