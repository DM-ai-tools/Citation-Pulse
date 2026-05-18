"""run_engines_parallel_task must not call asyncio.gather outside a running loop."""

from __future__ import annotations

import asyncio
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.tasks import geo  # noqa: E402


def test_run_engines_parallel_empty():
    assert geo.run_engines_parallel_task.run([]) == "empty"


def test_gather_wrapped_in_asyncio_run(monkeypatch):
    calls: list[str] = []

    def fake_run(coro):
        calls.append("run")
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    monkeypatch.setattr(geo.asyncio, "run", fake_run)
    monkeypatch.setattr(geo, "_execute_engine_run", lambda rid: "ok")

    geo.run_engines_parallel_task.run(["00000000-0000-4000-8000-000000000001"])
    assert calls == ["run"]
