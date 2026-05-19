"""Match AI competitor landscape to engine citations; rank by cross-engine visibility."""

from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from citationpulse.models.domain import Brand, Citation, EngineRun, Prompt, Scan
from citationpulse.services.normalization import registrable_domain
from citationpulse.services.ownership import classify_domain


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
        if not dom:
            continue
        out[dom] = {
            "domain": dom,
            "name": str(cb.name or dom),
            "tier": "You provided",
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


def _collect_engine_citations(
    cells: list[dict[str, Any]],
    *,
    engines: list[str],
    prompt_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Map registrable domain -> engine citation hits from report matrix cells."""
    by_domain: dict[str, list[dict[str, Any]]] = {}
    engine_set = set(engines)

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
            if not url:
                continue
            dom = registrable_domain(url)
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


def _build_visibility_payload(
    *,
    competitor_map: dict[str, dict[str, Any]],
    discovery_map: dict[str, dict[str, Any]],
    user_map: dict[str, dict[str, Any]],
    cells: list[dict[str, Any]],
    engines: list[str],
    prompt_text: str,
    prompt_id: str | None = None,
) -> dict[str, Any]:
    """Rank discovery + user-provided competitors against engine citations."""
    engine_by_domain = _collect_engine_citations(cells, engines=engines, prompt_id=prompt_id)
    all_domains = set(competitor_map.keys())
    total_engines = max(1, len(engines))

    ranked: list[dict[str, Any]] = []
    for dom in all_domains:
        meta = competitor_map.get(dom, {})
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
            if not eng:
                continue
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

    ranked.sort(
        key=lambda r: (
            -float(r["visibility_score"]),
            -int(r["engine_count"]),
            -int(r["citation_count"]),
            str(r["domain"]),
        )
    )
    for i, row in enumerate(ranked, start=1):
        row["visibility_rank"] = i

    discovery_only = [r for r in ranked if not r["cited_by_engines"]]
    cited_ranked = [r for r in ranked if r["cited_by_engines"]]
    user_provided_rows = [
        {"domain": r["domain"], "name": r["name"]}
        for r in ranked
        if r.get("user_provided")
    ]

    out: dict[str, Any] = {
        "prompt_text": prompt_text,
        "engines": engines,
        "ranked_competitors": ranked,
        "competitors": cited_ranked,
        "user_provided_competitors": user_provided_rows,
        "discovery_matched_count": sum(1 for r in ranked if r.get("matched_in_discovery")),
        "user_provided_count": len(user_provided_rows),
        "engine_cited_count": sum(1 for r in ranked if r["cited_by_engines"]),
        "both_matched_count": sum(1 for r in ranked if r["cited_by_engines"]),
        "discovery_only": discovery_only,
        "other_cited_domains": [],
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
