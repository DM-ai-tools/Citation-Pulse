"""Match AI competitor landscape to engine citations; rank by cross-engine visibility."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from citationpulse.models.domain import (
    Brand,
    Citation,
    EngineRun,
    EngineType,
    Ownership,
    Prompt,
    RunStatus,
    Scan,
)
from citationpulse.services.normalization import registrable_domain
from citationpulse.services.ownership import classify_domain

# Tier-balanced cited competitors (expansion loop + UI display).
TARGET_SAME_TIER_MIN = 2
TARGET_ABOVE_TIER_MIN = 2
TARGET_SAME_TIER_MAX = 3
TARGET_ABOVE_TIER_MAX = 3
DISPLAY_MIN_COMPETITORS = TARGET_SAME_TIER_MIN + TARGET_ABOVE_TIER_MIN
DISPLAY_MAX_COMPETITORS = TARGET_SAME_TIER_MAX + TARGET_ABOVE_TIER_MAX


def reclassify_scan_citations(db: Session, scan: Scan) -> int:
    """Re-tag citation ownership after competitor brands are linked (discovery finished)."""
    brand_id = scan.brand_id
    if not brand_id:
        return 0
    brand = db.get(Brand, brand_id)
    if not brand:
        return 0
    runs = list(db.scalars(select(EngineRun).where(EngineRun.scan_id == scan.id)).all())
    updated = 0
    for run in runs:
        prompt = db.get(Prompt, run.prompt_id)
        if not prompt:
            continue
        cites = list(db.scalars(select(Citation).where(Citation.engine_run_id == run.id)).all())
        for c in cites:
            new_own = classify_domain(db, brand.tenant_id, c.url, brand.id)
            if c.ownership != new_own:
                c.ownership = new_own
                updated += 1
    if updated:
        db.flush()
    return updated


def _discovery_competitor_map(
    discovery: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """domain -> merged competitor metadata from discovery JSON."""
    if not isinstance(discovery, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}

    def add_row(row: dict[str, Any], *, level: str) -> None:
        dom = registrable_domain(
            str(row.get("domain") or "")
            if str(row.get("domain", "")).startswith("http")
            else f"https://{row.get('domain', '')}"
        )
        if not dom:
            return
        cites = row.get("citations") if isinstance(row.get("citations"), list) else []
        out[dom] = {
            "domain": dom,
            "name": str(row.get("name") or dom),
            "tier": str(row.get("tier") or ""),
            "level": level,
            "discovery_rank": row.get("rank"),
            "rank_reason": row.get("rank_reason"),
            "reasoning": str(row.get("reasoning") or ""),
            "authority_advantage": str(row.get("authority_advantage") or ""),
            "similarity_score": row.get("similarity_score"),
            "citation_strength_score": row.get("citation_strength_score"),
            "discovery_citations": cites,
        }

    for row in discovery.get("same_level_competitors") or []:
        if isinstance(row, dict):
            add_row(row, level="same_level")
    for row in discovery.get("one_level_above_competitors") or []:
        if isinstance(row, dict):
            add_row(row, level="one_level_above")
    return out


def _user_provided_competitor_map(db: Session, brand: Brand | None) -> dict[str, dict[str, Any]]:
    """Domains the user listed when starting the scan (linked ``brand.competitors``)."""
    if not brand or not brand.competitors:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for cid in brand.competitors:
        cb = db.get(Brand, cid)
        if not cb:
            continue
        raw_dom = (cb.domains[0] if cb.domains else cb.name) or ""
        dom = registrable_domain(
            raw_dom if str(raw_dom).startswith("http") else f"https://{raw_dom}"
        )
        if not dom and "." in str(raw_dom):
            dom = registrable_domain(f"https://{str(raw_dom).strip().lstrip('www.')}")
        if not dom:
            continue
        out[dom] = {
            "domain": dom,
            "name": str(cb.name or dom),
            "tier": "4",
            "level": "user_provided",
            "discovery_rank": None,
            "rank_reason": None,
            "reasoning": "Competitor domain you entered when starting this scan.",
            "authority_advantage": "",
            "similarity_score": None,
            "citation_strength_score": None,
            "discovery_citations": [],
            "user_provided": True,
        }
    return out


def _merge_competitor_source_maps(
    discovery_map: dict[str, dict[str, Any]],
    user_map: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Union of AI discovery and user-provided competitors (user flag preserved on overlap)."""
    merged = {dom: dict(meta) for dom, meta in discovery_map.items()}
    for dom, meta in user_map.items():
        if dom in merged:
            merged[dom] = {**merged[dom], "user_provided": True}
        else:
            merged[dom] = dict(meta)
    return merged


def _expand_tracked_domains(domains: set[str]) -> set[str]:
    """Normalize user-entered domains (e.g. Service.com.au) for citation matching."""
    out: set[str] = set()
    for raw in domains:
        if not raw:
            continue
        d = raw.strip().lower()
        out.add(d)
        url = d if d.startswith(("http://", "https://")) else f"https://{d}"
        reg = registrable_domain(url)
        if reg:
            out.add(reg)
        if d.startswith("www."):
            out.add(d[4:])
    return out


def _merge_citation_hits(
    base: dict[str, list[dict[str, Any]]],
    extra: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    merged = {k: list(v) for k, v in base.items()}
    for dom, hits in extra.items():
        if dom not in merged:
            merged[dom] = []
        seen = {(h.get("engine"), h.get("url")) for h in merged[dom]}
        for h in hits:
            key = (h.get("engine"), h.get("url"))
            if key not in seen:
                merged[dom].append(h)
                seen.add(key)
    return merged


def _collect_engine_citations_from_db(
    db: Session,
    scan: Scan,
    *,
    engines: list[str],
    prompt_id: str | None = None,
    tracked_competitor_domains: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """All persisted citations for this scan (not limited to 8 per matrix cell)."""
    tracked = _expand_tracked_domains(tracked_competitor_domains or set())
    engine_set = set(engines)
    by_domain: dict[str, list[dict[str, Any]]] = {}
    runs = list(db.scalars(select(EngineRun).where(EngineRun.scan_id == scan.id)).all())

    for run in runs:
        if run.status != RunStatus.OK.value:
            continue
        eng = run.engine.value if isinstance(run.engine, EngineType) else str(run.engine)
        if eng and eng not in engine_set:
            continue
        if prompt_id is not None and str(run.prompt_id) != prompt_id:
            continue
        cites = list(db.scalars(select(Citation).where(Citation.engine_run_id == run.id)).all())
        for c in cites:
            url = str(c.url or "").strip()
            dom = (c.domain or registrable_domain(url)).lower()
            if not url or not dom:
                continue
            tagged = str(c.ownership or "") == Ownership.COMPETITOR.value
            on_tracked = dom in tracked
            if not tagged and not on_tracked:
                continue
            hit = {
                "engine": eng,
                "url": url,
                "ownership": str(c.ownership or "neutral"),
                "position": int(c.position) if c.position is not None else None,
                "snippet": (c.snippet or "")[:300] or None,
            }
            by_domain.setdefault(dom, []).append(hit)
    return by_domain


def _collect_engine_citations(
    cells: list[dict[str, Any]],
    *,
    engines: list[str],
    prompt_id: str | None = None,
    competitors_only: bool = False,
    tracked_competitor_domains: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Map registrable domain -> engine citation hits from report matrix cells."""
    by_domain: dict[str, list[dict[str, Any]]] = {}
    engine_set = set(engines)
    tracked = _expand_tracked_domains(tracked_competitor_domains or set())

    for cell in cells:
        if prompt_id is not None and str(cell.get("promptId") or "") != prompt_id:
            continue
        eng = str(cell.get("engine") or "")
        if eng and eng not in engine_set:
            continue
        for c in cell.get("citations") or []:
            if not isinstance(c, dict):
                continue
            url = str(c.get("url") or "").strip()
            dom = registrable_domain(url) if url else ""
            if competitors_only:
                tagged = str(c.get("ownership") or "") == "competitor"
                on_tracked = bool(dom and dom in tracked)
                if not tagged and not on_tracked:
                    continue
            if not url:
                continue
            if not dom:
                continue
            hit = {
                "engine": eng,
                "url": url,
                "ownership": str(c.get("ownership") or "neutral"),
                "position": c.get("position"),
                "snippet": (c.get("snippet") or "")[:300] or None,
            }
            by_domain.setdefault(dom, []).append(hit)
    return by_domain


def _collect_engine_citations_for_visibility(
    *,
    db: Session | None,
    scan: Scan | None,
    cells: list[dict[str, Any]],
    engines: list[str],
    prompt_id: str | None,
    tracked_competitor_domains: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Merge full DB citations with matrix cells (cells are capped at 8 URLs each)."""
    tracked = _expand_tracked_domains(tracked_competitor_domains)
    engine_by_domain: dict[str, list[dict[str, Any]]] = {}
    if db is not None and scan is not None:
        engine_by_domain = _collect_engine_citations_from_db(
            db,
            scan,
            engines=engines,
            prompt_id=prompt_id,
            tracked_competitor_domains=tracked,
        )
    from_cells = _collect_engine_citations(
        cells,
        engines=engines,
        prompt_id=prompt_id,
        competitors_only=True,
        tracked_competitor_domains=tracked,
    )
    engine_by_domain = _merge_citation_hits(engine_by_domain, from_cells)
    # Matrix cells omit neutral URLs beyond the top 8 — scan all cell citations for tracked domains.
    broad_cells = _collect_engine_citations(
        cells,
        engines=engines,
        prompt_id=prompt_id,
        competitors_only=False,
        tracked_competitor_domains=tracked,
    )
    for dom, hits in broad_cells.items():
        if dom in tracked:
            engine_by_domain = _merge_citation_hits(engine_by_domain, {dom: hits})
    return engine_by_domain


def _visibility_score(
    *,
    engine_count: int,
    total_engines: int,
    citation_count: int,
    best_position: int | None,
    discovery_strength: float | None,
    in_discovery: bool,
) -> float:
    eng_part = (engine_count / max(1, total_engines)) * 45.0
    cite_part = min(citation_count, 12) / 12.0 * 30.0
    pos_part = 0.0
    if best_position is not None and best_position > 0:
        pos_part = max(0.0, 15.0 - min(best_position - 1, 14))
    disc_part = (discovery_strength or (0.55 if in_discovery else 0.0)) * 10.0
    return round(min(100.0, eng_part + cite_part + pos_part + disc_part), 1)


def _is_valid_cited_competitor(row: dict[str, Any]) -> bool:
    """Cited by ≥1 engine with non-empty citation data (never show zero-citation rows)."""
    if not row.get("cited_by_engines"):
        return False
    hits = row.get("engine_citations")
    if isinstance(hits, list) and len(hits) > 0:
        return True
    cite_count = row.get("citation_count")
    if isinstance(cite_count, int) and cite_count > 0:
        return True
    by_eng = row.get("citations_by_engine")
    if isinstance(by_eng, dict):
        return any(isinstance(v, list) and len(v) > 0 for v in by_eng.values())
    return False


def _display_sort_key(row: dict[str, Any]) -> tuple[float | int | str, ...]:
    """Citation frequency → relevance (visibility) → discovery strength → citation count."""
    strength = row.get("citation_strength_score")
    if strength is None:
        strength = row.get("similarity_score")
    strength_f = float(strength) if isinstance(strength, (int, float)) else 0.0
    return (
        -int(row.get("engine_count") or 0),
        -float(row.get("visibility_score") or 0),
        -strength_f,
        -int(row.get("citation_count") or 0),
        str(row.get("domain") or ""),
    )


def _count_cited_by_tier(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Count valid cited competitors by discovery tier (same-level vs one-level-above)."""
    same = above = 0
    for row in rows:
        if not _is_valid_cited_competitor(row):
            continue
        level = str(row.get("level") or "")
        if level == "same_level":
            same += 1
        elif level == "one_level_above":
            above += 1
    return same, above


def _tier_balance_shortfall(rows: list[dict[str, Any]]) -> list[str]:
    """Tiers that still need more cited competitors (for expansion targeting)."""
    same, above = _count_cited_by_tier(rows)
    missing: list[str] = []
    if same < TARGET_SAME_TIER_MIN:
        missing.append("same_level")
    if above < TARGET_ABOVE_TIER_MIN:
        missing.append("one_level_above")
    return missing


def _tier_balance_meta(rows: list[dict[str, Any]]) -> dict[str, Any]:
    same, above = _count_cited_by_tier(rows)
    return {
        "same_tier_cited": same,
        "one_above_tier_cited": above,
        "same_tier_min": TARGET_SAME_TIER_MIN,
        "one_above_tier_min": TARGET_ABOVE_TIER_MIN,
        "same_tier_max": TARGET_SAME_TIER_MAX,
        "one_above_tier_max": TARGET_ABOVE_TIER_MAX,
        "tier_targets_met": same >= TARGET_SAME_TIER_MIN and above >= TARGET_ABOVE_TIER_MIN,
        "missing_tiers": _tier_balance_shortfall(rows),
    }


def tier_balance_shortfall_for_visibility(visibility: dict[str, Any]) -> list[str]:
    """
    Prompt IDs (or ``__aggregate__``) that still need tier-balanced cited competitors.

    Checks each ``by_prompt`` block; falls back to aggregate ranked pool when no per-prompt data.
    """
    prompts = visibility.get("by_prompt")
    if isinstance(prompts, list) and prompts:
        short: list[str] = []
        for block in prompts:
            if not isinstance(block, dict):
                continue
            pool = block.get("all_ranked_competitors") or block.get("ranked_competitors") or []
            if _tier_balance_shortfall(pool):
                pid = str(block.get("prompt_id") or "")
                short.append(pid or "__aggregate__")
        return short
    pool = visibility.get("all_ranked_competitors") or visibility.get("ranked_competitors") or []
    if _tier_balance_shortfall(pool):
        return ["__aggregate__"]
    return []


def _engine_positions_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-engine best citation position for API/UI consumers."""
    by_engine = row.get("citations_by_engine")
    if not isinstance(by_engine, dict):
        return []
    detail: list[dict[str, Any]] = []
    for eng, hits in by_engine.items():
        if not isinstance(hits, list) or not hits:
            continue
        positions = [int(h["position"]) for h in hits if isinstance(h, dict) and isinstance(h.get("position"), int)]
        detail.append(
            {
                "engine": str(eng),
                "position": min(positions) if positions else None,
            }
        )
    detail.sort(key=lambda x: str(x.get("engine") or ""))
    return detail


def _sanitize_cited_engines(row: dict[str, Any]) -> None:
    """Only retain engines that actually cited this competitor (no empty columns)."""
    by_engine = row.get("citations_by_engine")
    if not isinstance(by_engine, dict):
        by_engine = {}
    cited_map = {
        eng: cites
        for eng, cites in by_engine.items()
        if isinstance(cites, list) and len(cites) > 0
    }
    # Rebuild from engine_citations if citations_by_engine was empty but hits exist
    if not cited_map and row.get("engine_citations"):
        for h in row["engine_citations"]:
            if not isinstance(h, dict):
                continue
            eng = str(h.get("engine") or "")
            if not eng:
                continue
            cited_map.setdefault(eng, []).append(h)
    row["citations_by_engine"] = cited_map
    cited_list = sorted(cited_map.keys())
    row["engines"] = cited_list
    row["cited_engines"] = cited_list
    row["engine_count"] = len(cited_list)
    row["citation_count"] = sum(len(v) for v in cited_map.values())


def _apply_discovery_level(
    row: dict[str, Any],
    discovery_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Ensure cited rows use discovery tier (not generic engine_cited)."""
    dom = str(row.get("domain") or "").lower()
    meta = discovery_map.get(dom)
    if not meta:
        return row
    out = dict(row)
    level = meta.get("level")
    if level in ("same_level", "one_level_above"):
        out["level"] = level
    if meta.get("tier"):
        out["tier"] = meta.get("tier")
    if meta.get("name"):
        out["name"] = meta.get("name")
    out["matched_in_discovery"] = True
    return out


def _display_cited_competitors(
    ranked: list[dict[str, Any]],
    *,
    discovery_map: dict[str, dict[str, Any]] | None = None,
    max_same: int = TARGET_SAME_TIER_MAX,
    max_above: int = TARGET_ABOVE_TIER_MAX,
) -> list[dict[str, Any]]:
    """
    UI list: cited competitors only, tier-balanced (up to 3 same-tier + 3 one-level-above).

    User-provided competitors are included when cited, after tier slots are filled.
    """
    dmap = discovery_map or {}
    valid = [_apply_discovery_level(r, dmap) for r in ranked if _is_valid_cited_competitor(r)]
    valid.sort(key=_display_sort_key)

    same = [r for r in valid if r.get("level") == "same_level"]
    above = [r for r in valid if r.get("level") == "one_level_above"]
    user = [r for r in valid if r.get("level") == "user_provided"]
    other = [
        r
        for r in valid
        if r.get("level") not in ("same_level", "one_level_above", "user_provided")
    ]

    out: list[dict[str, Any]] = []

    def append_row(row: dict[str, Any]) -> None:
        r = dict(row)
        r["visibility_rank"] = len(out) + 1
        _sanitize_cited_engines(r)
        r["cited_engines_detail"] = _engine_positions_from_row(r)
        if r.get("cited_engines"):
            out.append(r)

    for row in same[:max_same]:
        append_row(row)
    for row in above[:max_above]:
        append_row(row)
    for row in user + other:
        if len(out) >= DISPLAY_MAX_COMPETITORS:
            break
        if row["domain"] in {x["domain"] for x in out}:
            continue
        append_row(row)

    return out


def _build_visibility_payload(
    *,
    competitor_map: dict[str, dict[str, Any]],
    discovery_map: dict[str, dict[str, Any]],
    user_map: dict[str, dict[str, Any]],
    cells: list[dict[str, Any]],
    engines: list[str],
    prompt_text: str,
    prompt_id: str | None = None,
    db: Session | None = None,
    scan: Scan | None = None,
) -> dict[str, Any]:
    """Rank discovery + user-provided competitors against engine citations."""
    tracked_domains = set(competitor_map.keys())
    engine_by_domain = _collect_engine_citations_for_visibility(
        db=db,
        scan=scan,
        cells=cells,
        engines=engines,
        prompt_id=prompt_id,
        tracked_competitor_domains=tracked_domains,
    )
    # Include every competitor domain engines cited for this prompt (no fetch cap).
    all_domains = set(competitor_map.keys()) | set(engine_by_domain.keys())
    total_engines = max(1, len(engines))

    ranked: list[dict[str, Any]] = []
    for dom in all_domains:
        meta = competitor_map.get(dom) or {
            "domain": dom,
            "name": dom,
            "tier": "",
            "level": "engine_cited",
            "discovery_rank": None,
            "reasoning": "Cited by at least one AI engine for this prompt.",
            "authority_advantage": "",
            "similarity_score": None,
            "citation_strength_score": None,
            "discovery_citations": [],
        }
        in_discovery = dom in discovery_map
        user_provided = bool(meta.get("user_provided") or dom in user_map)
        hits = engine_by_domain.get(dom, [])
        engines_seen = sorted({str(h["engine"]) for h in hits})
        positions = [int(h["position"]) for h in hits if isinstance(h.get("position"), int)]
        best_pos = min(positions) if positions else None
        disc_strength = meta.get("citation_strength_score")
        if isinstance(disc_strength, (int, float)):
            disc_strength = float(disc_strength)
        elif user_provided:
            disc_strength = 0.5
        else:
            disc_strength = None

        score = _visibility_score(
            engine_count=len(engines_seen),
            total_engines=total_engines,
            citation_count=len(hits),
            best_position=best_pos,
            discovery_strength=disc_strength,
            in_discovery=in_discovery or user_provided,
        )
        citations_by_engine: dict[str, list[dict[str, Any]]] = {}
        for h in hits:
            eng = str(h.get("engine") or "")
            if eng:
                citations_by_engine.setdefault(eng, []).append(h)

        ranked.append(
            {
                "domain": dom,
                "name": meta.get("name") or dom,
                "tier": meta.get("tier") or "",
                "level": meta.get("level"),
                "discovery_rank": meta.get("discovery_rank"),
                "visibility_score": score,
                "engine_count": len(engines_seen),
                "citation_count": len(hits),
                "engines": engines_seen,
                "cited_engines": engines_seen,
                "best_position": best_pos,
                "matched_in_discovery": in_discovery,
                "user_provided": user_provided,
                "cited_by_engines": len(hits) > 0,
                "reasoning": meta.get("reasoning") or "",
                "authority_advantage": meta.get("authority_advantage"),
                "discovery_citations": meta.get("discovery_citations") or [],
                "engine_citations": hits,
                "citations_by_engine": citations_by_engine,
            }
        )

    ranked.sort(key=_display_sort_key)
    for i, row in enumerate(ranked, start=1):
        row["visibility_rank"] = i

    discovery_only = [r for r in ranked if not r["cited_by_engines"]]
    display_competitors = _display_cited_competitors(ranked, discovery_map=discovery_map)
    tier_balance = _tier_balance_meta(
        [_apply_discovery_level(r, discovery_map) for r in ranked if r.get("cited_by_engines")]
    )
    user_provided_rows = [
        {"domain": r["domain"], "name": r["name"]}
        for r in ranked
        if r.get("user_provided")
    ]

    out: dict[str, Any] = {
        "prompt_text": prompt_text,
        "engines": engines,
        "ranked_competitors": display_competitors,
        "competitors": display_competitors,
        "all_ranked_competitors": ranked,
        "user_provided_competitors": user_provided_rows,
        "discovery_matched_count": sum(1 for r in ranked if r.get("matched_in_discovery")),
        "user_provided_count": len(user_provided_rows),
        "engine_cited_count": len(display_competitors),
        "both_matched_count": len(display_competitors),
        "discovery_only": discovery_only,
        "other_cited_domains": [
            r
            for r in ranked
            if r.get("cited_by_engines")
            and r["domain"] not in {d["domain"] for d in display_competitors}
        ],
        "display_count": len(display_competitors),
        "display_min_target": DISPLAY_MIN_COMPETITORS,
        "display_max_limit": DISPLAY_MAX_COMPETITORS,
        "total_cited_pool": sum(1 for r in ranked if r.get("cited_by_engines")),
        "tier_balance": tier_balance,
    }
    if prompt_id:
        out["prompt_id"] = prompt_id
    return out


def build_competitor_citation_visibility(
    db: Session,
    scan: Scan,
    *,
    cells: list[dict[str, Any]],
    engines: list[str],
    competitor_discovery: dict[str, Any] | None,
    prompts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Connect competitor landscape domains to engine citations; rank by visibility.

    Uses discovery JSON + live matrix cells (post-reclassification when possible).
    Includes ``by_prompt`` when multiple prompts exist (per-prompt toggle in UI).
    """
    brand = db.get(Brand, scan.brand_id) if scan.brand_id else None
    discovery_map = _discovery_competitor_map(competitor_discovery)
    user_map = _user_provided_competitor_map(db, brand)
    competitor_map = _merge_competitor_source_maps(discovery_map, user_map)
    prompt_rows = [p for p in (prompts or []) if isinstance(p, dict) and p.get("id")]

    payload_kw = dict(
        competitor_map=competitor_map,
        discovery_map=discovery_map,
        user_map=user_map,
        cells=cells,
        engines=engines,
        db=db,
        scan=scan,
    )

    by_prompt: list[dict[str, Any]] = []
    for p in prompt_rows:
        pid = str(p.get("id") or "")
        if not pid:
            continue
        by_prompt.append(
            _build_visibility_payload(
                **payload_kw,
                prompt_text=str(p.get("text") or ""),
                prompt_id=pid,
            )
        )

    prompt_text = str((prompt_rows[0] or {}).get("text") or "") if prompt_rows else ""
    result = _build_visibility_payload(**payload_kw, prompt_text=prompt_text)
    if by_prompt:
        result["by_prompt"] = by_prompt
    return result
