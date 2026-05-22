"""Post-scan competitor discovery expansion until strict 2+2 multi-AI validation passes."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from citationpulse.constants.competitor_targets import MAX_COMPETITOR_VALIDATION_ROUNDS
from citationpulse.models.domain import Brand, Scan
from citationpulse.schemas.competitors import CompetitorAnalyzeRequest
from citationpulse.services.competitor_discovery import (
    CompetitorDiscoveryError,
    discovery_domains,
    expand_competitors,
    merge_competitor_discovery,
)
from citationpulse.services.competitor_discovery_scan import (
    _ensure_competitor_brands,
    _locale_to_market,
    auto_discover_enabled,
)
from citationpulse.services.competitor_citation_visibility import reclassify_scan_citations
from citationpulse.services.competitor_final_selection import run_validation_until_satisfied

_log = logging.getLogger(__name__)


def _all_domains_for_scan(
    discovery: dict[str, Any],
    db: Session,
    scan: Scan,
) -> set[str]:
    domains = set(discovery_domains(discovery))
    brand = db.get(Brand, scan.brand_id) if scan.brand_id else None
    if brand and brand.competitors:
        from citationpulse.services.competitor_citation_visibility import _user_provided_competitor_map

        domains |= set(_user_provided_competitor_map(db, brand).keys())
    return domains


def _analyze_request_from_scan(scan: Scan) -> CompetitorAnalyzeRequest:
    params = scan.discovery_params if isinstance(scan.discovery_params, dict) else {}
    return CompetitorAnalyzeRequest(
        target_website=scan.submitted_url,
        competitor_type=params.get("competitor_type"),
        service=params.get("service"),
        niche=params.get("niche"),
        location=params.get("location"),
        excluded_competitors=list(params.get("excluded_competitors") or []),
        market=str(params.get("market") or _locale_to_market(scan.locale)),
    )


def _ensure_brands_from_addon(db: Session, scan: Scan, addon: Any) -> None:
    brand = db.get(Brand, scan.brand_id)
    if not brand:
        return
    new_domains = list(discovery_domains(addon))
    _ensure_competitor_brands(
        db,
        tenant_id=brand.tenant_id,
        main_brand=brand,
        domains=new_domains,
    )


def enrich_competitor_discovery_for_scan(
    db: Session,
    scan: Scan,
    *,
    cells: list[dict[str, Any]],
    engines: list[str],
    prompts: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    Keep fetching and cross-checking until every prompt satisfies:
    2 same-tier + 2 competitors ahead, 4 total, each cited by ≥2 distinct AIs on that prompt.
    """
    raw = scan.competitor_discovery
    if not isinstance(raw, dict) or not raw:
        return raw

    discovery: dict[str, Any] = dict(raw)
    if not auto_discover_enabled(scan):
        return discovery

    brand = db.get(Brand, scan.brand_id)
    if not brand:
        return discovery

    req = _analyze_request_from_scan(scan)

    def _expand(req_: CompetitorAnalyzeRequest, *, existing_domains: set[str], missing_tiers: list[str]):
        return expand_competitors(
            req_,
            existing_domains=existing_domains,
            missing_tiers=missing_tiers,
        )

    discovery = run_validation_until_satisfied(
        db,
        scan,
        cells=cells,
        engines=engines,
        prompts=prompts,
        discovery=discovery,
        analyze_request=req,
        expand_fn=_expand,
        merge_fn=merge_competitor_discovery,
        all_domains_fn=_all_domains_for_scan,
        ensure_brands_fn=_ensure_brands_from_addon,
        max_rounds=MAX_COMPETITOR_VALIDATION_ROUNDS,
    )
    scan.competitor_discovery = discovery
    db.flush()
    return discovery


def enrich_competitor_discovery_after_scan_complete(db: Session, scan_id: UUID) -> None:
    """Fast post-scan pass: reclassify citations and cache visibility (optional light expansion)."""
    scan = db.get(Scan, scan_id)
    if not scan or scan.status != "completed":
        return

    from citationpulse.services.scans_flow import build_scan_competitor_citations, build_scan_snapshot

    snap = build_scan_snapshot(db, scan)
    cells = list((snap.get("matrix") or {}).get("cells") or [])
    engines = list(snap.get("engines") or [])
    prompts = list(snap.get("prompts") or [])
    params = scan.discovery_params if isinstance(scan.discovery_params, dict) else {}

    try:
        reclassify_scan_citations(db, scan)
        if isinstance(scan.competitor_discovery, dict) and scan.competitor_discovery:
            try:
                enrich_competitor_discovery_for_scan(
                    db,
                    scan,
                    cells=cells,
                    engines=engines,
                    prompts=prompts,
                )
            except Exception:
                _log.warning(
                    "post-scan competitor expansion skipped scan_id=%s (using existing discovery)",
                    scan_id,
                )
        build_scan_competitor_citations(db, scan)
        p = dict(params)
        p["report_enriched"] = True
        scan.discovery_params = p
        db.commit()
    except Exception:
        _log.exception("enrich_competitor_discovery_after_scan_complete scan_id=%s", scan_id)
        db.rollback()
