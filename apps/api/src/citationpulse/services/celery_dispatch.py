"""Dispatch Celery tasks in a way that works with ``task_always_eager`` (local API) and workers."""

from __future__ import annotations

from celery import Celery


def dispatch_task(celery_app: Celery, name: str, args: list | None = None, kwargs: dict | None = None):
    """Prefer the registered task's ``delay`` so eager mode runs inline; fall back to ``send_task``."""
    args = args or []
    kwargs = kwargs or {}
    try:
        task = celery_app.tasks.get(name)
        if task is not None:
            return task.delay(*args, **kwargs)
    except Exception:
        pass
    return celery_app.send_task(name, args=args, kwargs=kwargs)
