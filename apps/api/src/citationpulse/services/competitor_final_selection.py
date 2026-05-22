"""Strict 2+2 competitor selection with per-prompt multi-AI citation verification."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from citationpulse.constants.competitor_targets import (
    MAX_COMPETITOR_VALIDATION_ROUNDS,
    MIN_CITATION_HITS_PER_PROMPT,
    MIN_ENGINE_CITATIONS,
    ONE_LEVEL_ABOVE_COUNT,
    SAME_LEVEL_COUNT,
    TOTAL_COMPETITOR_COUNT,
)
from citationpulse.models.domain import Scan
from citationpulse.services.competitor_citation_visibility import (
    _apply_discovery_level,
    _display_sort_key,
    _discovery_competitor_map,
    build_competitor_citation_visibility,
    reclassify_scan_citations,
)
from citationpulse.services.normalization import registrable_domain

_log = logging.getLogger(__name__)


def meets_strict_ai_engine_threshold(
    row: dict[str, Any],
    *,
    min_engines: int = MIN_ENGINE_CITATIONS,
) -> bool:
    """True when ≥ ``min_engines`` distinct AI engines cited this domain on the current prompt."""
    if not row.get("cited_by_engines"):
        return False
    engine_count = int(row.get("engine_count") or 0)
    if engine_count >= min_engines:
        return True
    by_engine = row.get("citations_by_engine")
    if isinstance(by_engine, dict):
        engines_with_hits = sum(
            1 for v in by_engine.values() if isinstance(v, list) and len(v) > 0
        )
        return engines_with_hits >= min_engines
    return False


def meets_prompt_citation_threshold(
    row: dict[str, Any],
    *,
    min_engines: int = MIN_ENGINE_CITATIONS,
    min_hits: int = MIN_CITATION_HITS_PER_PROMPT,
    strict_engines_only: bool = False,
) -> bool:
    """Per-prompt threshold; strict mode requires distinct AI engines only."""
    if strict_engines_only:
        return meets_strict_ai_engine_threshold(row, min_engines=min_engines)
    if not row.get("cited_by_engines"):
        return False
    if meets_strict_ai_engine_threshold(row, min_engines=min_engines):
        return True
    return int(row.get("citation_count") or 0) >= min_hits


def meets_multi_engine_threshold(row: dict[str, Any], *, min_engines: int = MIN_ENGINE_CITATIONS) -> bool:
    return meets_strict_ai_engine_threshold(row, min_engines=min_engines)


def _domain_from_row(row: dict[str, Any]) -> str:
    raw = str(row.get("domain") or "")
    if not raw:
        return ""
    return registrable_domain(raw if raw.startswith("http") else f"https://{raw}") or raw.lower()


def _visibility_prompt_blocks(visibility: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = visibility.get("by_prompt")
    if isinstance(blocks, list) and blocks:
        return [b for b in blocks if isinstance(b, dict)]
    return [visibility] if isinstance(visibility, dict) else []


def select_final_competitors(
    ranked: list[dict[str, Any]],
    discovery_map: dict[str, dict[str, Any]],
    *,
    max_same: int = SAME_LEVEL_COUNT,
    max_above: int = ONE_LEVEL_ABOVE_COUNT,
    allow_tier_fill: bool = False,
) -> list[dict[str, Any]]:
    """
    Select exactly up to ``max_same`` + ``max_above`` competitors that pass strict multi-AI rules.
    """
    pool = [
        _apply_discovery_level(dict(r), discovery_map)
        for r in ranked
        if meets_prompt_citation_threshold(r, strict_engines_only=True)
    ]
    pool.sort(key=_display_sort_key)

    same = [r for r in pool if r.get("level") == "same_level"]
    above = [r for r in pool if r.get("level") == "one_level_above"]
    other = [r for r in pool if r.get("level") not in ("same_level", "one_level_above")]

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def take(rows: list[dict[str, Any]], limit: int) -> None:
        for row in rows:
            if len(selected) >= TOTAL_COMPETITOR_COUNT:
                return
            dom = _domain_from_row(row)
            if not dom or dom in seen:
                continue
            if len([s for s in selected if s.get("level") == row.get("level")]) >= limit:
                continue
            seen.add(dom)
            selected.append(row)

    take(same, max_same)
    take(above, max_above)

    if allow_tier_fill:
        def fill_shortfall(level: str, cap: int, candidates: list[dict[str, Any]]) -> None:
            have = len([s for s in selected if s.get("level") == level])
            need = cap - have
            if need <= 0:
                return
            for row in candidates:
                if need <= 0:
                    break
                dom = _domain_from_row(row)
                if not dom or dom in seen:
                    continue
                if not meets_strict_ai_engine_threshold(row):
                    continue
                patched = dict(row)
                patched["level"] = level
                seen.add(dom)
                selected.append(patched)
                need -= 1

        discovery_other = [r for r in other if r.get("matched_in_discovery")]
        fill_shortfall("same_level", max_same, discovery_other + same)
        fill_shortfall("one_level_above", max_above, discovery_other + above)

    return selected[:TOTAL_COMPETITOR_COUNT]


def verify_final_competitors(
    selected: list[dict[str, Any]],
    *,
    max_same: int = SAME_LEVEL_COUNT,
    max_above: int = ONE_LEVEL_ABOVE_COUNT,
) -> dict[str, Any]:
    """Mandatory checks: 2 same + 2 above, 4 total, each with ≥2 AI engines."""
    same = [r for r in selected if r.get("level") == "same_level"]
    above = [r for r in selected if r.get("level") == "one_level_above"]
    issues: list[str] = []

    if len(same) != max_same:
        issues.append(f"same-level count {len(same)} != required {max_same}")
    if len(above) != max_above:
        issues.append(f"competitors ahead count {len(above)} != required {max_above}")
    if len(selected) != TOTAL_COMPETITOR_COUNT:
        issues.append(f"total count {len(selected)} != required {TOTAL_COMPETITOR_COUNT}")

    for row in selected:
        dom = _domain_from_row(row) or "unknown"
        if not meets_strict_ai_engine_threshold(row):
            issues.append(
                f"{dom}: cited by {row.get('engine_count') or 0} AI(s); requires ≥{MIN_ENGINE_CITATIONS}"
            )

    targets_met = not issues
    return {
        "ok": targets_met,
        "targets_met": targets_met,
        "same_level_count": len(same),
        "one_level_above_count": len(above),
        "total_count": len(selected),
        "target_same": max_same,
        "target_above": max_above,
        "target_total": TOTAL_COMPETITOR_COUNT,
        "min_engine_citations": MIN_ENGINE_CITATIONS,
        "every_competitor_multi_ai": all(meets_strict_ai_engine_threshold(r) for r in selected),
        "issues": issues,
    }


def evaluate_prompt_block(
    block: dict[str, Any],
    discovery_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Run filter → select → verify for one prompt's ranked pool."""
    ranked = list(block.get("all_ranked_competitors") or [])
    selected = select_final_competitors(ranked, discovery_map, allow_tier_fill=False)
    verification = verify_final_competitors(selected)
    return {
        "prompt_id": block.get("prompt_id"),
        "selected": selected,
        "verification": verification,
    }


def strict_requirements_met(
    visibility: dict[str, Any],
    discovery_map: dict[str, dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    """
    True only when every prompt block passes mandatory 2+2 multi-AI validation.
    """
    evaluations = [evaluate_prompt_block(b, discovery_map) for b in _visibility_prompt_blocks(visibility)]
    all_ok = bool(evaluations) and all(
        e["verification"]["ok"] for e in evaluations  # type: ignore[index]
    )
    return all_ok, {
        "all_requirements_met": all_ok,
        "per_prompt": [
            {
                "prompt_id": e.get("prompt_id"),
                "ok": e["verification"]["ok"],  # type: ignore[index]
                "verification": e["verification"],
            }
            for e in evaluations
        ],
    }


def _merge_best_global_selection(
    evaluations: list[dict[str, Any]],
    discovery_map: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge per-prompt picks, then enforce global 2+2 with strict verification."""
    merged_by_domain: dict[str, dict[str, Any]] = {}
    for ev in evaluations:
        for row in ev.get("selected") or []:
            if not isinstance(row, dict):
                continue
            dom = _domain_from_row(row)
            if not dom:
                continue
            score = float(row.get("visibility_score") or 0)
            prev = merged_by_domain.get(dom)
            if not prev or score > float(prev.get("visibility_score") or 0):
                merged_by_domain[dom] = row

    selected = select_final_competitors(
        list(merged_by_domain.values()),
        discovery_map,
        allow_tier_fill=False,
    )
    verification = verify_final_competitors(selected)
    return selected, verification


def cap_discovery_lists(discovery: dict[str, Any]) -> dict[str, Any]:
    out = dict(discovery)
    out["same_level_competitors"] = list(out.get("same_level_competitors") or [])[:SAME_LEVEL_COUNT]
    out["one_level_above_competitors"] = list(out.get("one_level_above_competitors") or [])[
        :ONE_LEVEL_ABOVE_COUNT
    ]
    summary = out.get("validation_summary")
    if isinstance(summary, dict):
        vs = dict(summary)
        vs["same_level_validated"] = len(out["same_level_competitors"])
        vs["one_level_above_validated"] = len(out["one_level_above_competitors"])
        out["validation_summary"] = vs
    return out


def trim_discovery_json(
    discovery: dict[str, Any],
    *,
    same_domains: list[str],
    above_domains: list[str],
) -> dict[str, Any]:
    out = dict(discovery)

    def pick_rows(key: str, allowed: list[str]) -> list[dict[str, Any]]:
        order = {d.lower(): i for i, d in enumerate(allowed)}
        rows: list[dict[str, Any]] = []
        for row in discovery.get(key) or []:
            if not isinstance(row, dict):
                continue
            dom = _domain_from_row(row)
            if dom and dom.lower() in order:
                rows.append(dict(row))
        rows.sort(key=lambda r: order.get(_domain_from_row(r).lower(), 999))
        return rows

    out["same_level_competitors"] = pick_rows("same_level_competitors", same_domains)
    out["one_level_above_competitors"] = pick_rows("one_level_above_competitors", above_domains)
    return cap_discovery_lists(out)


def _verification_notes(verification: dict[str, Any], *, complete: bool) -> str:
    if complete and verification.get("ok"):
        return (
            f"All validation checks passed: {verification['same_level_count']} same-level, "
            f"{verification['one_level_above_count']} competitors ahead ({verification['total_count']} total); "
            f"each cited by ≥{MIN_ENGINE_CITATIONS} distinct AIs on the prompt."
        )
    issues = verification.get("issues") or []
    base = (
        f"Validation incomplete: {verification.get('same_level_count', 0)}/{SAME_LEVEL_COUNT} same-level, "
        f"{verification.get('one_level_above_count', 0)}/{ONE_LEVEL_ABOVE_COUNT} competitors ahead "
        f"(need {TOTAL_COMPETITOR_COUNT} total with ≥{MIN_ENGINE_CITATIONS} AIs each). "
        "Continuing competitor fetch cycles."
    )
    if issues:
        return f"{base} Issues: {'; '.join(issues[:6])}"
    return base


def apply_final_competitor_selection(
    db: Session,
    scan: Scan,
    *,
    cells: list[dict[str, Any]],
    engines: list[str],
    prompts: list[dict[str, Any]] | None = None,
    discovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Cross-check engine citations per prompt; trim discovery to 2+2 only when ALL checks pass.
    """
    raw = discovery if discovery is not None else scan.competitor_discovery
    if not isinstance(raw, dict) or not raw:
        return raw or {}

    discovery_in = dict(raw)
    reclassify_scan_citations(db, scan)

    visibility = build_competitor_citation_visibility(
        db,
        scan,
        cells=cells,
        engines=engines,
        competitor_discovery=discovery_in,
        prompts=prompts,
    )
    discovery_map = _discovery_competitor_map(discovery_in)

    full_evals = [evaluate_prompt_block(b, discovery_map) for b in _visibility_prompt_blocks(visibility)]
    all_ok = bool(full_evals) and all(e["verification"]["ok"] for e in full_evals)
    strict_meta = {
        "all_requirements_met": all_ok,
        "per_prompt": [
            {
                "prompt_id": e.get("prompt_id"),
                "ok": e["verification"]["ok"],
                "verification": e["verification"],
            }
            for e in full_evals
        ],
    }
    selected, verification = _merge_best_global_selection(full_evals, discovery_map)
    # Completion requires every prompt to pass 2+2 × ≥2 AIs (not only a global merge).
    complete = all_ok

    if complete:
        same_domains: list[str] = []
        above_domains: list[str] = []
        seen_same: set[str] = set()
        seen_above: set[str] = set()
        for ev in full_evals:
            for row in ev.get("selected") or []:
                dom = _domain_from_row(row)
                if not dom:
                    continue
                if row.get("level") == "same_level" and dom not in seen_same:
                    seen_same.add(dom)
                    same_domains.append(dom)
                elif row.get("level") == "one_level_above" and dom not in seen_above:
                    seen_above.add(dom)
                    above_domains.append(dom)
        same_domains = same_domains[:SAME_LEVEL_COUNT]
        above_domains = above_domains[:ONE_LEVEL_ABOVE_COUNT]
        trimmed = trim_discovery_json(
            discovery_in,
            same_domains=[d for d in same_domains if d],
            above_domains=[d for d in above_domains if d],
        )
    else:
        trimmed = discovery_in

    summary = trimmed.get("validation_summary")
    if not isinstance(summary, dict):
        summary = {}
    else:
        summary = dict(summary)
    summary["final_verification"] = verification
    summary["strict_validation"] = strict_meta
    summary["validation_complete"] = complete
    summary["notes"] = _verification_notes(verification, complete=complete)
    trimmed["validation_summary"] = summary

    scan.competitor_discovery = trimmed
    params = scan.discovery_params if isinstance(scan.discovery_params, dict) else {}
    p = dict(params)
    p["competitors_validation_complete"] = complete
    p["final_verification"] = verification
    p["strict_validation"] = strict_meta
    scan.discovery_params = p
    from citationpulse.services.competitor_visibility_cache import store_competitor_visibility_cache

    store_competitor_visibility_cache(scan, visibility, db=db, discovery=trimmed)
    db.flush()

    _log.info(
        "competitor final selection scan_id=%s complete=%s same=%s above=%s total=%s",
        scan.id,
        complete,
        verification.get("same_level_count"),
        verification.get("one_level_above_count"),
        verification.get("total_count"),
    )
    return trimmed


def run_validation_until_satisfied(
    db: Session,
    scan: Scan,
    *,
    cells: list[dict[str, Any]],
    engines: list[str],
    prompts: list[dict[str, Any]] | None,
    discovery: dict[str, Any],
    analyze_request: Any,
    expand_fn: Any,
    merge_fn: Any,
    all_domains_fn: Any,
    ensure_brands_fn: Any,
    max_rounds: int = MAX_COMPETITOR_VALIDATION_ROUNDS,
) -> dict[str, Any]:
    """
    Retrieval-validation loop: expand discovery until strict 2+2 multi-AI checks pass on every prompt.
    """
    current = dict(discovery)
    rounds = 0

    while rounds < max_rounds:
        reclassify_scan_citations(db, scan)
        current = apply_final_competitor_selection(
            db,
            scan,
            cells=cells,
            engines=engines,
            prompts=prompts,
            discovery=current,
        )
        db.refresh(scan)
        params = scan.discovery_params if isinstance(scan.discovery_params, dict) else {}
        if params.get("competitors_validation_complete"):
            _log.info("strict competitor validation satisfied scan_id=%s rounds=%s", scan.id, rounds)
            return current

        existing = all_domains_fn(current, db, scan)
        before = len(existing)
        missing_tiers: list[str] = ["same_level", "one_level_above"]
        try:
            addon = expand_fn(analyze_request, existing_domains=existing, missing_tiers=missing_tiers)
        except Exception as exc:
            _log.warning("validation loop expansion stopped scan_id=%s: %s", scan.id, exc)
            break

        current = merge_fn(current, addon)
        after = len(all_domains_fn(current, db, scan))
        if after <= before:
            _log.info("validation loop: no new domains scan_id=%s round=%s", scan.id, rounds)
            break

        scan.competitor_discovery = current
        ensure_brands_fn(db, scan, addon)
        reclassify_scan_citations(db, scan)
        rounds += 1
        p = dict(params)
        p["validation_rounds"] = rounds
        scan.discovery_params = p
        db.flush()
        _log.info(
            "validation loop round=%s scan_id=%s domains=%s complete=%s",
            rounds,
            scan.id,
            after,
            params.get("competitors_validation_complete"),
        )

    return current
