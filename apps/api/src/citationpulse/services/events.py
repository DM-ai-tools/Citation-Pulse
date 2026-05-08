from __future__ import annotations

import logging
import uuid
from typing import Any

from citationpulse.db.session import SessionLocal
from citationpulse.models.domain import ScanEvent

_log = logging.getLogger(__name__)


def publish_scan_event(scan_id: str, event: dict[str, Any]) -> None:
    """Append a scan-progress event row. The SSE endpoint long-polls `scan_events`
    keyed on `(scan_id, id)` and fans rows out to the browser as `text/event-stream`.

    Fire-and-forget: any error (DB blip, transient lock) is swallowed so worker
    tasks don't fail just because the live UI lost an event.
    """
    try:
        sid = uuid.UUID(scan_id) if not isinstance(scan_id, uuid.UUID) else scan_id
        db = SessionLocal()
        try:
            db.add(ScanEvent(scan_id=sid, payload=event))
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        _log.debug("scan event persist skipped: %s", exc)
