"""Cache competitor citation visibility on scan.discovery_params to avoid rebuilding every report GET."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from citationpulse.models.domain import Scan

_CACHE_KEY = "competitor_citation_visibility_cache"

# Bump when the visibility-builder output shape or filter policy changes so stale caches
# from prior code versions are invalidated automatically (e.g., broadening non-brand collection).
_BUILDER_VERSION = "v3-matrix-sync"


def visibility_cache_fingerprint(
    db: Session,
    scan: Scan,
    discovery: dict[str, Any] | None,
) -> str:
    """Invalidate when runs, discovery lists, validation state, or builder version change."""
    from citationpulse.services.scans_flow import count_terminal_runs_for_scan

    terminal, total = count_terminal_runs_for_scan(db, scan.id)
    disc = discovery if isinstance(discovery, dict) else {}
    vs = disc.get("validation_summary") if isinstance(disc.get("validation_summary"), dict) else {}
    params = scan.discovery_params if isinstance(scan.discovery_params, dict) else {}
    return "|".join(
        [
            _BUILDER_VERSION,
            str(scan.completed_at or ""),
            f"{terminal}/{total}",
            str(vs.get("validation_complete")),
            str(len(disc.get("same_level_competitors") or [])),
            str(len(disc.get("one_level_above_competitors") or [])),
            str(params.get("validation_rounds") or 0),
            str(params.get("competitors_validation_complete")),
        ]
    )


def load_cached_competitor_visibility(
    db: Session,
    scan: Scan,
    discovery: dict[str, Any] | None,
) -> dict[str, Any] | None:
    params = scan.discovery_params if isinstance(scan.discovery_params, dict) else {}
    cache = params.get(_CACHE_KEY)
    if not isinstance(cache, dict):
        return None
    payload = cache.get("payload")
    if not isinstance(payload, dict):
        return None
    fp = visibility_cache_fingerprint(db, scan, discovery)
    if cache.get("fingerprint") == fp:
        return payload
    return None


def store_competitor_visibility_cache(
    scan: Scan,
    visibility: dict[str, Any],
    *,
    db: Session,
    discovery: dict[str, Any] | None = None,
) -> None:
    params = dict(scan.discovery_params) if isinstance(scan.discovery_params, dict) else {}
    fp = visibility_cache_fingerprint(db, scan, discovery)
    params[_CACHE_KEY] = {"fingerprint": fp, "payload": visibility}
    scan.discovery_params = params
