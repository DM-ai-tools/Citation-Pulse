"""Multi-entity share-of-voice: brand + each linked competitor, from citation domains on the primary brand's prompts."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from citationpulse.models.domain import Brand, Citation, EngineRun, EngineType, Prompt
from citationpulse.models.domain import all_engines
from citationpulse.services.normalization import registrable_domain


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _norm_host(domain_field: str) -> str:
    d = (domain_field or "").strip().lower()
    if not d:
        return ""
    if "://" in d:
        return registrable_domain(d)
    return registrable_domain(f"https://{d}")


def _build_domain_to_entity(primary: Brand, competitors: dict[UUID, Brand]) -> dict[str, str]:
    """Map registrable domain -> entity key ``brand`` or ``competitor:<uuid>`` (first match wins)."""
    out: dict[str, str] = {}
    for raw in primary.domains or []:
        dom = _norm_host(raw)
        if dom:
            out.setdefault(dom, "brand")
    for cid, comp in competitors.items():
        for raw in comp.domains or []:
            dom = _norm_host(raw)
            if dom:
                out.setdefault(dom, f"competitor:{cid}")
    return out


def _bucket_key(domain_field: str, domain_map: dict[str, str]) -> str:
    dom = _norm_host(domain_field)
    if dom and dom in domain_map:
        return domain_map[dom]
    return "other"


def _canonical_engine_key(raw: object) -> str | None:
    """Map ORM / driver engine values to ``EngineType.value`` (e.g. ``chatgpt``).

    Prefer the ORM enum instance (``EngineRun.engine``) in queries so we never depend on
    ``cast(..., String)``, which varies by dialect (labels vs values, odd SQLite casts).
    """
    if raw is None:
        return None
    if isinstance(raw, EngineType):
        return raw.value
    s = str(raw).strip()
    if not s:
        return None
    low = s.lower()
    for e in EngineType:
        if s == e.value or low == e.value.lower():
            return e.value
        if s == e.name or low == e.name.lower():
            return e.value
    return None


def multientity_sov_by_engine(
    db: Session,
    tenant_id: UUID,
    primary_brand_id: UUID,
    days: int,
) -> dict[str, object]:
    """Per-engine share = entity citation count / all citations on that engine (same window, primary brand prompts)."""
    primary = db.get(Brand, primary_brand_id)
    if not primary or primary.tenant_id != tenant_id:
        return {"error": "not_found"}

    competitors: dict[UUID, Brand] = {}
    for cid in primary.competitors or []:
        c = db.get(Brand, cid)
        if c and c.tenant_id == tenant_id:
            competitors[cid] = c

    domain_map = _build_domain_to_entity(primary, competitors)
    since = _since(days)

    stmt = (
        select(EngineRun.engine, Citation.domain, func.count(Citation.id))
        .select_from(Citation)
        .join(EngineRun, Citation.engine_run_id == EngineRun.id)
        .join(Prompt, EngineRun.prompt_id == Prompt.id)
        .join(Brand, Prompt.brand_id == Brand.id)
        .where(Brand.tenant_id == tenant_id, Brand.id == primary_brand_id)
        .where(EngineRun.finished_at.is_not(None))
        .where(EngineRun.finished_at >= since)
        .group_by(EngineRun.engine, Citation.domain)
    )

    # counts[engine][bucket] = n
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for eng, dom, cnt in db.execute(stmt):
        eng_key = _canonical_engine_key(eng)
        if eng_key is None:
            continue
        key = _bucket_key(str(dom), domain_map)
        counts[eng_key][key] += int(cnt)

    engines = all_engines()
    entity_rows: list[dict[str, object]] = [
        {"entity_id": str(primary.id), "name": primary.name, "role": "brand", "shares_by_engine": {}},
    ]
    for cid, comp in competitors.items():
        entity_rows.append(
            {"entity_id": str(cid), "name": comp.name, "role": "competitor", "shares_by_engine": {}},
        )

    for eng in engines:
        per_b = counts.get(eng, {})
        total = sum(per_b.values()) or 1
        # brand
        entity_rows[0]["shares_by_engine"][eng] = round(per_b.get("brand", 0) / total, 4)
        for i, (cid, _) in enumerate(competitors.items(), start=1):
            bkey = f"competitor:{cid}"
            entity_rows[i]["shares_by_engine"][eng] = round(per_b.get(bkey, 0) / total, 4)
        # optional: expose "other" share on primary row? skip for now

    brand_citations = sum(int(counts.get(eng, {}).get("brand", 0)) for eng in engines)
    competitor_citations = sum(
        int(counts.get(eng, {}).get(f"competitor:{cid}", 0)) for eng in engines for cid in competitors
    )

    return {
        "primary_brand_id": str(primary.id),
        "range_days": days,
        "engines": engines,
        "entities": entity_rows,
        "totals": {
            "brand_citations": brand_citations,
            "competitor_citations": competitor_citations,
        },
    }


def entity_weekly_share_trend(
    db: Session,
    tenant_id: UUID,
    primary_brand_id: UUID,
    focus_entity_id: UUID,
    weeks: int = 12,
) -> dict[str, object]:
    """Weekly share for one entity (primary brand or a linked competitor): matching-domain citations / all citations."""
    primary = db.get(Brand, primary_brand_id)
    if not primary or primary.tenant_id != tenant_id:
        return {"error": "not_found"}

    if focus_entity_id == primary_brand_id:
        domain_set = {_norm_host(d) for d in (primary.domains or []) if _norm_host(d)}
    else:
        if focus_entity_id not in (primary.competitors or []):
            return {"error": "invalid_entity"}
        comp = db.get(Brand, focus_entity_id)
        if not comp or comp.tenant_id != tenant_id:
            return {"error": "invalid_entity"}
        domain_set = {_norm_host(d) for d in (comp.domains or []) if _norm_host(d)}

    since = datetime.now(timezone.utc) - timedelta(weeks=weeks + 1)

    wk_col = func.date_trunc("week", EngineRun.finished_at)
    stmt = (
        select(wk_col, Citation.domain, func.count(Citation.id))
        .select_from(Citation)
        .join(EngineRun, Citation.engine_run_id == EngineRun.id)
        .join(Prompt, EngineRun.prompt_id == Prompt.id)
        .join(Brand, Prompt.brand_id == Brand.id)
        .where(Brand.tenant_id == tenant_id, Brand.id == primary_brand_id)
        .where(EngineRun.finished_at.is_not(None))
        .where(EngineRun.finished_at >= since)
        .group_by(wk_col, Citation.domain)
        .order_by(wk_col)
    )

    per_week_total: dict[datetime, int] = defaultdict(int)
    per_week_match: dict[datetime, int] = defaultdict(int)
    for wk, dom, cnt in db.execute(stmt):
        if wk is None:
            continue
        c = int(cnt)
        per_week_total[wk] += c
        if domain_set and _norm_host(str(dom)) in domain_set:
            per_week_match[wk] += c

    series: list[dict[str, object]] = []
    for wk in sorted(per_week_total.keys()):
        tot = per_week_total[wk] or 1
        week_label = wk.date().isoformat() if isinstance(wk, datetime) else str(wk)
        series.append(
            {
                "week_start": week_label,
                "share": round(per_week_match[wk] / tot, 4),
            }
        )

    return {
        "primary_brand_id": str(primary_brand_id),
        "focus_entity_id": str(focus_entity_id),
        "weeks": weeks,
        "series": series,
    }


def multi_entity_weekly_share_trend(
    db: Session,
    tenant_id: UUID,
    primary_brand_id: UUID,
    weeks: int = 12,
) -> dict[str, object]:
    """Weekly share for brand + each competitor among tracked-domain citations only (excludes third-party).

    For each ISO week, share = entity citations ÷ (brand + all linked competitor citations) on the primary brand's prompts.
    """
    primary = db.get(Brand, primary_brand_id)
    if not primary or primary.tenant_id != tenant_id:
        return {"error": "not_found"}

    competitors: dict[UUID, Brand] = {}
    for cid in primary.competitors or []:
        c = db.get(Brand, cid)
        if c and c.tenant_id == tenant_id:
            competitors[cid] = c

    domain_map = _build_domain_to_entity(primary, competitors)
    since = datetime.now(timezone.utc) - timedelta(weeks=weeks + 1)

    wk_col = func.date_trunc("week", EngineRun.finished_at)
    stmt = (
        select(wk_col, Citation.domain, func.count(Citation.id))
        .select_from(Citation)
        .join(EngineRun, Citation.engine_run_id == EngineRun.id)
        .join(Prompt, EngineRun.prompt_id == Prompt.id)
        .join(Brand, Prompt.brand_id == Brand.id)
        .where(Brand.tenant_id == tenant_id, Brand.id == primary_brand_id)
        .where(EngineRun.finished_at.is_not(None))
        .where(EngineRun.finished_at >= since)
        .group_by(wk_col, Citation.domain)
        .order_by(wk_col)
    )

    per_week_bucket: dict[datetime, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for wk, dom, cnt in db.execute(stmt):
        if wk is None:
            continue
        key = _bucket_key(str(dom), domain_map)
        per_week_bucket[wk][key] += int(cnt)

    ordered_weeks = sorted(per_week_bucket.keys())
    if len(ordered_weeks) > weeks:
        ordered_weeks = ordered_weeks[-weeks:]

    entities_meta: list[dict[str, str]] = [
        {"entity_id": str(primary.id), "name": primary.name, "role": "brand"},
    ]
    for cid, comp in competitors.items():
        entities_meta.append({"entity_id": str(cid), "name": comp.name, "role": "competitor"})

    series_out: list[dict[str, object]] = []
    for wk in ordered_weeks:
        buckets = dict(per_week_bucket[wk])
        brand_n = int(buckets.get("brand", 0))
        comp_ns = {cid: int(buckets.get(f"competitor:{cid}", 0)) for cid in competitors}
        tracked = brand_n + sum(comp_ns.values())
        shares: dict[str, float] = {}
        if tracked > 0:
            shares[str(primary.id)] = round(brand_n / tracked, 4)
            for cid in competitors:
                shares[str(cid)] = round(comp_ns.get(cid, 0) / tracked, 4)
        else:
            shares[str(primary.id)] = 0.0
            for cid in competitors:
                shares[str(cid)] = 0.0
        week_label = wk.date().isoformat() if isinstance(wk, datetime) else str(wk)
        series_out.append({"week_start": week_label, "shares": shares, "tracked_citations": tracked})

    return {
        "primary_brand_id": str(primary_brand_id),
        "weeks": weeks,
        "entities": entities_meta,
        "series": series_out,
    }
