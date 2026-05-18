"""Tiny JSON cache facade — Redis when ``REDIS_URL`` is configured, otherwise in-process.

Why a thin facade and not raw redis-py everywhere?
  * Existing infra is Postgres-only (Celery broker, rate limits). Redis is optional.
  * Tests / dev should not need a Redis server running.
  * DataForSEO bills per lookup, so we cache by (variant, locale) for 7 days.

Public API:
    get_json(key)               -> dict | list | None
    set_json(key, value, ttl_s) -> None
    delete(key)                 -> None
    cache_configured()          -> bool   (True when Redis is reachable)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process LRU-ish fallback. Bounded by ``_MAX_ENTRIES``; entries expire on get.
# Keyed by full string key so it survives across function calls in the same worker.
# ---------------------------------------------------------------------------
_MAX_ENTRIES = 2048
_local_lock = threading.RLock()
_local_store: dict[str, tuple[float, str]] = {}  # key -> (expires_at_epoch, json_blob)


def _local_gc_locked() -> None:
    """Drop expired entries; if still over capacity, drop oldest by expiry."""
    if not _local_store:
        return
    now = time.time()
    expired = [k for k, (exp, _) in _local_store.items() if exp <= now]
    for k in expired:
        _local_store.pop(k, None)
    if len(_local_store) > _MAX_ENTRIES:
        # Drop ~10% oldest by expires_at.
        n_drop = max(1, len(_local_store) // 10)
        for k, _ in sorted(_local_store.items(), key=lambda kv: kv[1][0])[:n_drop]:
            _local_store.pop(k, None)


# ---------------------------------------------------------------------------
# Optional Redis client. Lazy-imported so the package works without ``redis``.
# ---------------------------------------------------------------------------
_redis_client: Any | None = None
_redis_probed: bool = False


def _redis_url() -> str:
    """Read ``REDIS_URL`` lazily.

    Order:
      1. ``REDIS_URL`` env var (works in any context, incl. plain scripts).
      2. ``Settings.redis_url`` (so pydantic .env loading also wires it in).
    """
    raw = (os.environ.get("REDIS_URL") or "").strip()
    if raw:
        return raw
    try:
        from citationpulse.core.config import get_settings

        return (get_settings().redis_url or "").strip()
    except Exception:  # noqa: BLE001 — keep cache import-safe in tests/scripts
        return ""


def _get_redis() -> Any | None:
    """Lazy-init a redis-py client; return None when unavailable.

    Connection errors are logged once and the cache falls back to in-process
    storage. We don't crash the pipeline because DataForSEO caching is a cost
    optimisation, not a correctness requirement.
    """
    global _redis_client, _redis_probed
    if _redis_probed:
        return _redis_client
    _redis_probed = True
    url = _redis_url()
    if not url:
        _redis_client = None
        return None
    try:
        import redis  # type: ignore

        # ``decode_responses=True`` so the JSON blob is a str, not bytes.
        client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2.0)
        client.ping()
        _redis_client = client
        _log.info("citationpulse.cache: connected to Redis at %s", url.split("@")[-1])
    except Exception as exc:  # noqa: BLE001
        _log.warning("citationpulse.cache: Redis unavailable (%s); using in-process fallback", exc)
        _redis_client = None
    return _redis_client


def cache_configured() -> bool:
    """True when a Redis backend is reachable (used for /health output)."""
    return _get_redis() is not None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_json(key: str) -> Any | None:
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            _log.warning("cache.get_json redis error key=%s: %s", key, exc)
            # fall through to in-process
    with _local_lock:
        entry = _local_store.get(key)
        if not entry:
            return None
        exp, blob = entry
        if exp <= time.time():
            _local_store.pop(key, None)
            return None
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            _local_store.pop(key, None)
            return None


def set_json(key: str, value: Any, ttl_s: int) -> None:
    if ttl_s <= 0:
        return
    blob = json.dumps(value, separators=(",", ":"), default=str)
    r = _get_redis()
    if r is not None:
        try:
            r.set(key, blob, ex=int(ttl_s))
            return
        except Exception as exc:  # noqa: BLE001
            _log.warning("cache.set_json redis error key=%s: %s", key, exc)
    with _local_lock:
        _local_store[key] = (time.time() + float(ttl_s), blob)
        _local_gc_locked()


def delete(key: str) -> None:
    r = _get_redis()
    if r is not None:
        try:
            r.delete(key)
        except Exception:  # noqa: BLE001
            pass
    with _local_lock:
        _local_store.pop(key, None)


def reset_for_tests() -> None:
    """Wipe local state. Tests call this between cases; production never does."""
    global _redis_client, _redis_probed
    _redis_probed = False
    _redis_client = None
    with _local_lock:
        _local_store.clear()
