"""Wire tiered competitor discovery into the funnel scan lifecycle."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from citationpulse.models.domain import Brand, Prompt, Scan
from citationpulse.schemas.competitors import CompetitorAnalyzeRequest, CompetitorDiscoveryResult
from citationpulse.services.competitor_discovery import (
    CompetitorDiscoveryError,
    analyze_competitors,
)
from citationpulse.services.competitor_discovery_limits import MAX_TRACKED_COMPETITOR_BRANDS
from citationpulse.services.normalization import registrable_domain

_log = logging.getLogger(__name__)


def _locale_to_market(locale: str) -> str:
    loc = (locale or "en-AU").lower()
    if loc.endswith("-au"):
        return "Australia"
    if loc.endswith("-gb"):
        return "United Kingdom"
    if loc.endswith("-us"):
        return "United States"
    if loc.endswith("-nz"):
        return "New Zealand"
    return "Australia"


def discovery_params_from_body(body: Any) -> dict[str, Any]:
    """Serialize optional discovery hints from POST /scans (stored until scan completes)."""
    auto = bool(getattr(body, "auto_discover_competitors", True))
    params: dict[str, Any] = {
        "auto_discover": auto,
        "competitor_type": getattr(body, "competitor_type", None),
        "service": (getattr(body, "service", None) or "").strip() or None,
        "niche": (getattr(body, "niche", None) or "").strip() or None,
        "location": (getattr(body, "location", None) or "").strip() or None,
        "excluded_competitors": [
            c.strip() for c in (getattr(body, "excluded_competitors", None) or []) if c.strip()
        ],
        "market": _locale_to_market(getattr(body, "locale", "en-AU")),
    }
    if auto:
        params["discovery_status"] = "pending"
    return params


def _collect_domains(result: CompetitorDiscoveryResult) -> list[str]:
    """Unique registrable domains from both competitor groups (order preserved)."""
    seen: set[str] = set()
    out: list[str] = []
    for row in list(result.same_level_competitors) + list(result.one_level_above_competitors):
        dom = registrable_domain(
            row.domain if row.domain.startswith("http") else f"https://{row.domain}"
        )
        if not dom or dom in seen:
            continue
        seen.add(dom)
        out.append(dom)
    return out


def _ensure_competitor_brands(
    db: Session,
    *,
    tenant_id: UUID,
    main_brand: Brand,
    domains: list[str],
) -> list[UUID]:
    """Create competitor Brand rows and attach up to 5 to main_brand.competitors."""
    if not domains:
        return list(main_brand.competitors or [])

    existing_ids = list(main_brand.competitors or [])
    existing_domains: set[str] = set()
    for cid in existing_ids:
        cb = db.get(Brand, cid)
        if cb and cb.domains:
            for d in cb.domains:
                existing_domains.add(d.lower())

    root = (main_brand.domains[0] if main_brand.domains else main_brand.name).lower()

    for dom in domains:
        if len(existing_ids) >= MAX_TRACKED_COMPETITOR_BRANDS:
            break
        if dom.lower() == root or dom.lower() in existing_domains:
            continue
        cb = Brand(tenant_id=tenant_id, name=dom, domains=[dom], competitors=[])
        db.add(cb)
        db.flush()
        existing_ids.append(cb.id)
        existing_domains.add(dom.lower())

    main_brand.competitors = existing_ids[:MAX_TRACKED_COMPETITOR_BRANDS]
    db.flush()
    return list(main_brand.competitors or [])


def run_competitor_discovery_for_scan(
    db: Session,
    scan: Scan,
    *,
    force: bool = False,
) -> CompetitorDiscoveryResult | None:
    """Run AI competitor discovery when scan completes; persist JSON on scan row.

    Skips when:
      - discovery already stored (unless force=True)
      - auto_discover is false in discovery_params
      - OpenRouter not configured (logged, returns None)
    """
    if scan.competitor_discovery and not force:
        return None

    params = scan.discovery_params if isinstance(scan.discovery_params, dict) else {}
    if not params.get("auto_discover", True):
        return None

    brand = db.get(Brand, scan.brand_id)
    if not brand:
        return None

    # Only explicit exclusions — never auto-exclude user-provided competitor brands.
    excluded = list(params.get("excluded_competitors") or [])

    req = CompetitorAnalyzeRequest(
        target_website=scan.submitted_url,
        competitor_type=params.get("competitor_type"),
        service=params.get("service"),
        niche=params.get("niche"),
        location=params.get("location"),
        excluded_competitors=excluded,
        market=str(params.get("market") or _locale_to_market(scan.locale)),
    )

    try:
        result = analyze_competitors(req)
    except CompetitorDiscoveryError as exc:
        _log.warning("competitor_discovery_for_scan failed scan_id=%s: %s", scan.id, exc)
        set_discovery_status(scan, "failed")
        db.flush()
        return None
    except Exception:
        _log.exception("competitor_discovery_for_scan failed scan_id=%s", scan.id)
        set_discovery_status(scan, "failed")
        db.flush()
        return None

    scan.competitor_discovery = result.model_dump(mode="json")
    set_discovery_status(scan, "done")
    domains = _collect_domains(result)
    _ensure_competitor_brands(db, tenant_id=brand.tenant_id, main_brand=brand, domains=domains)
    db.flush()
    return result


def _discovery_params(scan: Scan) -> dict[str, Any]:
    raw = scan.discovery_params
    return dict(raw) if isinstance(raw, dict) else {}


def set_discovery_status(scan: Scan, status: str) -> None:
    """Track background discovery lifecycle in ``discovery_params`` (no migration)."""
    params = _discovery_params(scan)
    params["discovery_status"] = status
    scan.discovery_params = params


def competitor_discovery_pending(scan: Scan) -> bool:
    """True while tiered discovery runs (before engine citation checks)."""
    if isinstance(scan.competitor_discovery, dict) and scan.competitor_discovery:
        return False
    params = _discovery_params(scan)
    if not params.get("auto_discover", True):
        return False
    status = params.get("discovery_status")
    if status in ("failed", "skipped", "done"):
        return False
    return status == "pending"


def auto_discover_enabled(scan: Scan) -> bool:
    params = _discovery_params(scan)
    return bool(params.get("auto_discover", True))


def competitor_discovery_for_report(scan: Scan) -> dict[str, object] | None:
    """Shape stored JSON for GET /scans/{id}/report."""
    raw = scan.competitor_discovery
    if not isinstance(raw, dict):
        return None
    return raw
