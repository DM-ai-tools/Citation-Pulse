from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from citationpulse.models.domain import Brand, Ownership
from citationpulse.services.normalization import registrable_domain


def classify_domain(
    db: Session,
    tenant_id: uuid.UUID,
    url: str,
    brand_id: uuid.UUID,
) -> str:
    """Map URL to ownership: brand | competitor | third_party | neutral."""
    dom = registrable_domain(url)
    brand = db.get(Brand, brand_id)
    if not brand or brand.tenant_id != tenant_id:
        return Ownership.NEUTRAL.value
    for d in brand.domains or []:
        if dom == registrable_domain(f"https://{d}") or dom.endswith("." + registrable_domain(f"https://{d}")):
            return Ownership.BRAND.value
    for cid in brand.competitors or []:
        comp = db.get(Brand, cid)
        if not comp or comp.tenant_id != tenant_id:
            continue
        for d in comp.domains or []:
            if dom == registrable_domain(f"https://{d}") or dom.endswith(
                "." + registrable_domain(f"https://{d}")
            ):
                return Ownership.COMPETITOR.value
    if dom in {"wikipedia.org", "reddit.com", "youtube.com"}:
        return Ownership.THIRD_PARTY.value
    return Ownership.NEUTRAL.value
