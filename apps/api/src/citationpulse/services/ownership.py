from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from citationpulse.models.domain import Brand, Ownership
from citationpulse.services.normalization import registrable_domain


def _root_for_domain_entry(raw: str) -> str:
    """Normalize a stored domain or URL to registrable root (works for any submitted URL shape)."""
    s = (raw or "").strip()
    if not s:
        return ""
    if not s.startswith(("http://", "https://")):
        s = f"https://{s.lstrip('/')}"
    return registrable_domain(s)


def _host_matches_brand_root(host: str, brand_root: str) -> bool:
    if not host or not brand_root:
        return False
    if host == brand_root:
        return True
    return host.endswith("." + brand_root)


def classify_domain(
    db: Session,
    tenant_id: uuid.UUID,
    url: str,
    brand_id: uuid.UUID,
) -> str:
    """Map URL to ownership: brand | competitor | third_party | neutral."""
    dom = registrable_domain(url)
    if not dom:
        return Ownership.NEUTRAL.value
    brand = db.get(Brand, brand_id)
    if not brand or brand.tenant_id != tenant_id:
        return Ownership.NEUTRAL.value
    for d in brand.domains or []:
        root = _root_for_domain_entry(d)
        if _host_matches_brand_root(dom, root):
            return Ownership.BRAND.value
    for cid in brand.competitors or []:
        comp = db.get(Brand, cid)
        if not comp or comp.tenant_id != tenant_id:
            continue
        for d in comp.domains or []:
            root = _root_for_domain_entry(d)
            if _host_matches_brand_root(dom, root):
                return Ownership.COMPETITOR.value
    if dom in {"wikipedia.org", "reddit.com", "youtube.com"}:
        return Ownership.THIRD_PARTY.value
    return Ownership.NEUTRAL.value
