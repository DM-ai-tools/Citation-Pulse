"""Celery inline / Railway deploy detection."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.core.config import Settings, celery_run_tasks_inline  # noqa: E402


def test_dev_defaults_inline():
    s = Settings(environment="development")
    assert celery_run_tasks_inline(s) is True


def test_production_without_worker_not_inline():
    s = Settings(environment="production")
    assert celery_run_tasks_inline(s) is False


def test_railway_api_only_inline(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("CELERY_USE_WORKER", raising=False)
    monkeypatch.delenv("CELERY_TASK_ALWAYS_EAGER", raising=False)
    s = Settings(environment="production")
    assert celery_run_tasks_inline(s) is True


def test_railway_with_worker_not_inline(monkeypatch):
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "api")
    monkeypatch.setenv("CELERY_USE_WORKER", "1")
    s = Settings(environment="production")
    assert celery_run_tasks_inline(s) is False


def test_force_eager(monkeypatch):
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "true")
    monkeypatch.setenv("CELERY_USE_WORKER", "1")
    s = Settings(environment="production")
    assert celery_run_tasks_inline(s) is True
