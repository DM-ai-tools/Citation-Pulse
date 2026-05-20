"""Post-scan competitor discovery expansion until tier-balanced cited minimums are met."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

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
from citationpulse.services.competitor_citation_visibility import (
    build_competitor_citation_visibility,
    reclassify_scan_citations,
    tier_balance_shortfall_for_visibility,
)

_log = logging.getLogger(__name__)

MAX_EXPANSION_ROUNDS = 5


def _missing_tiers_union(visibility: dict[str, Any]) -> list[str]:
    """Union of tiers still short across all prompt blocks (for targeted expansion)."""
    tiers: set[str] = set()
    by_prompt = visibility.get("by_prompt")
    if isinstance(by_prompt, list) and by_prompt:
        for block in by_prompt:
            if not isinstance(block, dict):
                continue
            tb = block.get("tier_balance")
            if isinstance(tb, dict):
                for t in tb.get("missing_tiers") or []:
                    if isinstance(t, str):
                        tiers.add(t)
        return sorted(tiers)
    tb = visibility.get("tier_balance")
    if isinstance(tb, dict):
        return [str(t) for t in (tb.get("missing_tiers") or []) if isinstance(t, str)]
    return []


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


def enrich_competitor_discovery_for_scan(
    db: Session,
    scan: Scan,
    *,
    cells: list[dict[str, Any]],
    engines: list[str],
    prompts: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    Expansion loop: widen discovery until each prompt has tier-balanced cited competitors
    (≥2 same-tier + ≥2 one-level-above cited, prefer up to 3+3) or expansion rounds exhausted.
    """
    raw = scan.competitor_discovery
    if not isinstance(raw, dict) or not raw:
        return raw

    discovery: dict[str, Any] = dict(raw)
    brand = db.get(Brand, scan.brand_id)
    if not brand:
        return discovery

    params = scan.discovery_params if isinstance(scan.discovery_params, dict) else {}
    if not auto_discover_enabled(scan):
        return discovery

    req = _analyze_request_from_scan(scan)
    rounds_done = int(params.get("expansion_rounds") or 0)

    for _ in range(MAX_EXPANSION_ROUNDS - rounds_done):
        reclassify_scan_citations(db, scan)
        visibility = build_competitor_citation_visibility(
            db,
            scan,
            cells=cells,
            engines=engines,
            competitor_discovery=discovery,
            prompts=prompts,
        )
        short_prompts = tier_balance_shortfall_for_visibility(visibility)
        if not short_prompts:
            break

        missing_tiers = _missing_tiers_union(visibility)
        if not missing_tiers:
            break

        existing = _all_domains_for_scan(discovery, db, scan)
        before = len(existing)
        try:
            addon = expand_competitors(
                req,
                existing_domains=existing,
                missing_tiers=missing_tiers,
            )
        except CompetitorDiscoveryError as exc:
            _log.warning(
                "competitor expansion stopped scan_id=%s round=%s: %s",
                scan.id,
                rounds_done,
                exc,
            )
            break
        except Exception:
            _log.exception("competitor expansion failed scan_id=%s", scan.id)
            break

        discovery = merge_competitor_discovery(discovery, addon)
        after = len(_all_domains_for_scan(discovery, db, scan))
        if after <= before:
            _log.info("competitor expansion: no new domains scan_id=%s", scan.id)
            break

        scan.competitor_discovery = discovery
        new_domains = list(discovery_domains(addon))
        _ensure_competitor_brands(
            db,
            tenant_id=brand.tenant_id,
            main_brand=brand,
            domains=new_domains,
        )
        reclassify_scan_citations(db, scan)
        rounds_done += 1
        params = dict(params)
        params["expansion_rounds"] = rounds_done
        scan.discovery_params = params
        db.flush()
        _log.info(
            "competitor expansion round=%s scan_id=%s domains=%s missing_tiers=%s prompts_short=%s",
            rounds_done,
            scan.id,
            after,
            missing_tiers,
            short_prompts,
        )

    scan.competitor_discovery = discovery
    db.flush()
    return discovery


def enrich_competitor_discovery_after_scan_complete(db: Session, scan_id: UUID) -> None:
    """Run expansion after all engine runs finish (called from ``maybe_complete_scan``)."""
    scan = db.get(Scan, scan_id)
    if not scan or scan.status != "completed":
        return
    if not isinstance(scan.competitor_discovery, dict) or not scan.competitor_discovery:
        return

    from citationpulse.services.scans_flow import build_scan_snapshot

    snap = build_scan_snapshot(db, scan)
    cells = list((snap.get("matrix") or {}).get("cells") or [])
    engines = list(snap.get("engines") or [])
    prompts = list(snap.get("prompts") or [])
    try:
        enrich_competitor_discovery_for_scan(
            db,
            scan,
            cells=cells,
            engines=engines,
            prompts=prompts,
        )
        db.commit()
    except Exception:
        _log.exception("enrich_competitor_discovery_after_scan_complete scan_id=%s", scan_id)
        db.rollback()
