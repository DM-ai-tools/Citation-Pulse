"""run_engines_parallel_task uses a thread pool (no asyncio.gather in the Celery task)."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.tasks import geo  # noqa: E402


def test_run_engines_parallel_empty():
    assert geo.run_engines_parallel_task.run([]) == "empty"


def test_runs_all_ids(monkeypatch):
    executed: list[str] = []

    def fake_execute(rid: str) -> str:
        executed.append(rid)
        return "ok"

    monkeypatch.setattr(geo, "_execute_engine_run", fake_execute)
    ids = [
        "00000000-0000-4000-8000-000000000001",
        "00000000-0000-4000-8000-000000000002",
    ]
    assert geo.run_engines_parallel_task.run(ids) == "ok"
    assert sorted(executed) == sorted(ids)
