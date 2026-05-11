from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from citationpulse.db.session import SessionLocal

_log = logging.getLogger(__name__)


_UPSERT_INCR_SQL = text(
    """
    INSERT INTO rate_limits (key, count, expires_at)
    VALUES (:key, 1, :expires_at)
    ON CONFLICT (key) DO UPDATE
       SET count = rate_limits.count + 1
    RETURNING count
    """
)


def _check_and_incr(key: str, limit: int, window_seconds: int) -> bool:
    """Atomic: increment counter for `key`, return True if still within `limit`.

    Fails open (returns True) if the DB is unavailable, matching the previous
    Redis behaviour — abuse protection should never block legitimate traffic.
    """
    try:
        db = SessionLocal()
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=window_seconds)
            result = db.execute(_UPSERT_INCR_SQL, {"key": key, "expires_at": expires_at})
            count = int(result.scalar_one())
            db.commit()
            return count <= limit
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        _log.debug("rate-limit check failed open: %s", exc)
        return True


def allow_anonymous_scan(client_ip: str, limit_per_hour: int = 8) -> bool:
    """Token bucket per IP for POST /scans (hour window)."""
    if limit_per_hour <= 0:
        return True
    ip = client_ip or "unknown"
    bucket = int(time.time() // 3600)
    return _check_and_incr(f"rl:anon_scan:{ip}:{bucket}", limit_per_hour, 3600)


def allow_ad_hoc_run(brand_id: str, limit_per_hour: int = 10) -> bool:
    """Token bucket per brand for POST /runs (hour window)."""
    bucket = int(time.time() // 3600)
    return _check_and_incr(f"rl:brand_run:{brand_id}:{bucket}", limit_per_hour, 3600)


def gc_expired_rate_limits() -> int:
    """Best-effort housekeeping: delete expired rows. Wire to Celery beat
    (e.g. every 30 min) if the table grows large; otherwise harmless to skip."""
    try:
        db = SessionLocal()
        try:
            n = db.execute(
                text("DELETE FROM rate_limits WHERE expires_at < now()")
            ).rowcount
            db.commit()
            return int(n or 0)
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        return 0
