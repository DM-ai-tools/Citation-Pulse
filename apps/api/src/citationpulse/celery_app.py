from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

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
celery_app.conf.update(
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
    task_routes={
        "citationpulse.run_engine": {"queue": "default"},
        "citationpulse.normalise": {"queue": "default"},
        "citationpulse.score": {"queue": "default"},
        "citationpulse.nightly_alerts": {"queue": "default"},
        "citationpulse.canary": {"queue": "default"},
        "citationpulse.fan_out_brand": {"queue": "default"},
        "citationpulse.fan_out_scan": {"queue": "default"},
        "citationpulse.daily_beat": {"queue": "default"},
    },
    beat_schedule={
        "citationpulse-daily": {
            "task": "citationpulse.daily_beat",
            "schedule": crontab(hour=2, minute=0),
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
