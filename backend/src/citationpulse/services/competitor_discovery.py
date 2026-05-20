"""Australian-market competitor discovery via OpenRouter (web-grounded JSON)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from citationpulse.core.config import Settings, get_settings
from citationpulse.prompts.competitor_discovery import build_competitor_discovery_messages
from citationpulse.schemas.competitors import (
    CompetitorAnalyzeRequest,
    CompetitorCitation,
    CompetitorDiscoveryResult,
    DiscoveryValidationSummary,
    OneLevelAboveCompetitor,
    SameLevelCompetitor,
    TargetCompanyAnalysis,
)
from citationpulse.services.llm_router import (
    LLMConfigError,
    LLMProviderError,
    chat_completion_sync,
    openrouter_configured,
)
from citationpulse.services.normalization import registrable_domain

_log = logging.getLogger(__name__)

# Initial discovery: 8–12 candidates (~50% same-tier, ~50% one-tier-above).
SAME_LEVEL_COUNT = 6
ONE_LEVEL_ABOVE_COUNT = 6
INITIAL_CANDIDATE_TARGET = SAME_LEVEL_COUNT + ONE_LEVEL_ABOVE_COUNT

# Expansion batch when tier-balanced cited minimums are not met.
EXPANSION_SAME_LEVEL_BATCH = 4
EXPANSION_ONE_LEVEL_ABOVE_BATCH = 4
EXPANSION_BATCH_SIZE = EXPANSION_SAME_LEVEL_BATCH + EXPANSION_ONE_LEVEL_ABOVE_BATCH

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

# Domains that must never appear as competitors (directories / aggregators / social).
_BLOCKED_DOMAIN_FRAGMENTS: frozenset[str] = frozenset(
    {
        "yellowpages",
        "yelp.",
        "truelocal",
        "hipages",
        "oneflare",
        "wordofmouth",
        "wikipedia.org",
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "amazon.",
        "ebay.",
        "gumtree.",
        "tripadvisor.",
        "hotfrog",
        "localsearch",
        "purelocal",
        "startlocal",
        "brownbook",
        "capterra",
        "g2.com",
        "clutch.co",
    }
)

_TIER_RE = re.compile(r"tier\s*(\d)", re.IGNORECASE)
_MIN_EVIDENCE_LEN = 8
_MIN_EVIDENCE_LEN_RELAXED = 3


class CompetitorDiscoveryError(RuntimeError):
    """User-visible failure (config, provider, or invalid model output)."""


def _strip_json_payload(text: str) -> str:
    """Extract a JSON object from model text (handles optional markdown fences)."""
    raw = (text or "").strip()
    if not raw:
        raise CompetitorDiscoveryError("Model returned empty response")
    raw = _JSON_FENCE_RE.sub("", raw).strip()
    if raw.startswith("{"):
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    raise CompetitorDiscoveryError("Model response did not contain a JSON object")


def _domain_key(domain: str) -> str:
    raw = (domain or "").strip()
    if not raw:
        return ""
    url = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
    return registrable_domain(url)


def _filter_excluded(
    payload: dict[str, Any],
    excluded: set[str],
) -> dict[str, Any]:
    """Remove excluded registrable domains from competitor lists."""
    if not excluded:
        return payload

    def keep_row(row: dict[str, Any]) -> bool:
        dom = _domain_key(str(row.get("domain") or ""))
        return dom not in excluded

    out = dict(payload)
    out["same_level_competitors"] = [
        r for r in (payload.get("same_level_competitors") or []) if isinstance(r, dict) and keep_row(r)
    ]
    out["one_level_above_competitors"] = [
        r
        for r in (payload.get("one_level_above_competitors") or [])
        if isinstance(r, dict) and keep_row(r)
    ]
    target = out.get("target_company")
    if isinstance(target, dict):
        td = _domain_key(str(target.get("domain") or ""))
        if td in excluded:
            raise CompetitorDiscoveryError("Target domain cannot be in excluded_competitors")
    return out


def _parse_tier(label: str) -> int | None:
    m = _TIER_RE.search(label or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _is_blocked_domain(domain: str) -> bool:
    d = (domain or "").lower()
    return any(frag in d for frag in _BLOCKED_DOMAIN_FRAGMENTS)


def _sanitize_citations(raw: list[dict[str, Any]], *, relaxed: bool = False) -> list[CompetitorCitation]:
    out: list[CompetitorCitation] = []
    seen_urls: set[str] = set()
    min_ev = _MIN_EVIDENCE_LEN_RELAXED if relaxed else _MIN_EVIDENCE_LEN
    for row in raw:
        if not isinstance(row, dict):
            continue
        url = (row.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            if url and "." in url:
                url = f"https://{url.lstrip('/')}"
            else:
                continue
        dom = registrable_domain(url)
        if not dom or _is_blocked_domain(dom):
            continue
        evidence = (row.get("evidence") or row.get("cited_text") or "").strip()
        if len(evidence) < min_ev:
            if relaxed and evidence:
                pass
            elif relaxed:
                evidence = f"Referenced page on {dom}."
            else:
                continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        rel = row.get("relevance_score")
        relevance = float(rel) if isinstance(rel, (int, float)) else None
        if relevance is not None:
            relevance = max(0.0, min(1.0, relevance))
        out.append(
            CompetitorCitation(
                type=str(row.get("type") or "seo_evidence"),
                url=url,
                evidence=evidence,
                relevance_score=relevance,
            )
        )
    out.sort(key=lambda c: -(c.relevance_score if c.relevance_score is not None else 0.5))
    return out


def _citations_for_row(row: dict[str, Any], dom: str) -> list[CompetitorCitation]:
    raw = list(row.get("citations") or [])
    cites = _sanitize_citations(raw)
    if not cites:
        cites = _sanitize_citations(raw, relaxed=True)
    if not cites:
        cites = [
            CompetitorCitation(
                type="homepage",
                url=f"https://{dom}/",
                evidence=str(row.get("reasoning") or row.get("authority_advantage") or "")[:400]
                or f"Competitor site for {dom}.",
                relevance_score=0.5,
            )
        ]
    return cites


def _citation_strength(citations: list[CompetitorCitation], base_score: float) -> float:
    if not citations:
        return 0.0
    rels = [c.relevance_score for c in citations if c.relevance_score is not None]
    avg_rel = sum(rels) / len(rels) if rels else 0.5
    volume = min(len(citations), 5) / 5.0
    return round(min(1.0, base_score * 0.45 + avg_rel * 0.35 + volume * 0.2), 3)


def _normalize_same_row(row: dict[str, Any], *, target_tier: int | None) -> SameLevelCompetitor | None:
    dom = _domain_key(str(row.get("domain") or ""))
    if not dom or _is_blocked_domain(dom):
        return None
    cites = _citations_for_row(row, dom)
    tier_num = _parse_tier(str(row.get("tier") or ""))
    if target_tier is not None and tier_num is not None and abs(tier_num - target_tier) > 1:
        return None
    # Trust same_level_competitors list when tier label missing or ambiguous.
    if target_tier is not None and tier_num is None:
        pass
    sim = float(row.get("similarity_score") or 0.5)
    sim = max(0.0, min(1.0, sim))
    strength = row.get("citation_strength_score")
    cite_strength = (
        float(strength)
        if isinstance(strength, (int, float))
        else _citation_strength(cites, sim)
    )
    cite_strength = max(0.0, min(1.0, cite_strength))
    return SameLevelCompetitor(
        domain=dom,
        name=str(row.get("name") or dom),
        tier=str(row.get("tier") or f"Tier {target_tier or 2}"),
        rank=None,
        rank_reason=(row.get("rank_reason") or None),
        similarity_score=sim,
        citation_strength_score=cite_strength,
        avg_position=row.get("avg_position"),
        intersections=row.get("intersections"),
        reasoning=str(row.get("reasoning") or ""),
        citations=cites,
    )


def _normalize_above_row(row: dict[str, Any], *, target_tier: int | None) -> OneLevelAboveCompetitor | None:
    dom = _domain_key(str(row.get("domain") or ""))
    if not dom or _is_blocked_domain(dom):
        return None
    cites = _citations_for_row(row, dom)
    tier_num = _parse_tier(str(row.get("tier") or ""))
    if target_tier is not None and tier_num is not None:
        if tier_num <= target_tier or tier_num > target_tier + 2:
            return None
    # Trust one_level_above_competitors list when tier label missing.
    elif target_tier is not None and tier_num is None:
        pass
    strength = row.get("citation_strength_score")
    cite_strength = (
        float(strength)
        if isinstance(strength, (int, float))
        else _citation_strength(cites, 0.65)
    )
    cite_strength = max(0.0, min(1.0, cite_strength))
    return OneLevelAboveCompetitor(
        domain=dom,
        name=str(row.get("name") or dom),
        tier=str(row.get("tier") or ""),
        rank=None,
        rank_reason=(row.get("rank_reason") or None),
        citation_strength_score=cite_strength,
        authority_advantage=str(row.get("authority_advantage") or ""),
        reasoning=str(row.get("reasoning") or ""),
        citations=cites,
    )


def _assign_ranks_same(rows: list[SameLevelCompetitor]) -> list[SameLevelCompetitor]:
    ordered = sorted(
        rows,
        key=lambda r: (-(r.citation_strength_score or 0), -r.similarity_score),
    )
    out: list[SameLevelCompetitor] = []
    for i, row in enumerate(ordered, start=1):
        out.append(
            row.model_copy(
                update={
                    "rank": i,
                    "rank_reason": row.rank_reason or f"Ranked #{i} by citation strength and similarity.",
                }
            )
        )
    return out


def _assign_ranks_above(rows: list[OneLevelAboveCompetitor]) -> list[OneLevelAboveCompetitor]:
    ordered = sorted(rows, key=lambda r: -(r.citation_strength_score or 0))
    out: list[OneLevelAboveCompetitor] = []
    for i, row in enumerate(ordered, start=1):
        out.append(
            row.model_copy(
                update={
                    "rank": i,
                    "rank_reason": row.rank_reason or f"Ranked #{i} by citation strength vs prompt.",
                }
            )
        )
    return out


def _finalize_discovery(
    data: dict[str, Any],
    *,
    excluded: set[str],
    same_level_cap: int = SAME_LEVEL_COUNT,
    one_level_above_cap: int = ONE_LEVEL_ABOVE_COUNT,
) -> CompetitorDiscoveryResult:
    """Validate, prune, rank, and normalize model JSON for UI display."""
    target_raw = data.get("target_company")
    if not isinstance(target_raw, dict):
        raise CompetitorDiscoveryError("Missing target_company in model JSON")
    target = TargetCompanyAnalysis.model_validate(target_raw)
    target_tier = _parse_tier(target.company_tier)

    same: list[SameLevelCompetitor] = []
    for row in data.get("same_level_competitors") or []:
        if isinstance(row, dict):
            parsed = _normalize_same_row(row, target_tier=target_tier)
            if parsed:
                same.append(parsed)
    same = _assign_ranks_same(same)[:same_level_cap]

    above: list[OneLevelAboveCompetitor] = []
    for row in data.get("one_level_above_competitors") or []:
        if isinstance(row, dict):
            parsed = _normalize_above_row(row, target_tier=target_tier)
            if parsed:
                above.append(parsed)
    above = _assign_ranks_above(above)[:one_level_above_cap]

    summary_raw = data.get("validation_summary")
    notes: list[str] = []
    if isinstance(summary_raw, dict) and summary_raw.get("notes"):
        notes.append(str(summary_raw["notes"]))
    if len(same) < same_level_cap:
        notes.append(f"Only {len(same)} same-level competitors passed validation (target {same_level_cap}).")
    if len(above) < one_level_above_cap:
        notes.append(
            f"Only {len(above)} one-level-above competitors passed validation (target {one_level_above_cap})."
        )

    summary = DiscoveryValidationSummary(
        same_level_validated=len(same),
        one_level_above_validated=len(above),
        citations_verified=all(r.citations for r in same + above),
        excluded_domains_removed=bool(excluded),
        notes=" ".join(notes).strip(),
    )

    if not same and not above:
        raise CompetitorDiscoveryError(
            "No competitors passed validation after OpenRouter response — check exclusions or retry."
        )

    result = CompetitorDiscoveryResult(
        target_company=target,
        same_level_competitors=same,
        one_level_above_competitors=above,
        validation_summary=summary,
    )
    return result


def discovery_domains(result: CompetitorDiscoveryResult | dict[str, Any]) -> set[str]:
    """Registrable domains from a discovery result (dict or model)."""
    if isinstance(result, CompetitorDiscoveryResult):
        rows = list(result.same_level_competitors) + list(result.one_level_above_competitors)
        return {d for d in (_domain_key(r.domain) for r in rows) if d}
    out: set[str] = set()
    for key in ("same_level_competitors", "one_level_above_competitors"):
        for row in result.get(key) or []:
            if isinstance(row, dict):
                dom = _domain_key(str(row.get("domain") or ""))
                if dom:
                    out.add(dom)
    return out


def merge_competitor_discovery(
    base: dict[str, Any],
    addon: CompetitorDiscoveryResult,
) -> dict[str, Any]:
    """Append expansion competitors to stored discovery JSON (dedupe by domain)."""
    out = dict(base)
    before = len(discovery_domains(out))
    seen = discovery_domains(out)

    def append_rows(key: str, rows: list[Any]) -> None:
        current = list(out.get(key) or [])
        for row in rows:
            payload = row.model_dump(mode="json") if hasattr(row, "model_dump") else row
            if not isinstance(payload, dict):
                continue
            dom = _domain_key(str(payload.get("domain") or ""))
            if not dom or dom in seen:
                continue
            seen.add(dom)
            current.append(payload)
        out[key] = current

    append_rows("same_level_competitors", list(addon.same_level_competitors))
    append_rows("one_level_above_competitors", list(addon.one_level_above_competitors))
    added = len(seen) - before
    summary = out.get("validation_summary")
    if isinstance(summary, dict) and added:
        summary = dict(summary)
        summary["notes"] = (
            str(summary.get("notes") or "").strip() + f" Expansion added {added} competitors."
        ).strip()
        out["validation_summary"] = summary
    return out


def expand_competitors(
    body: CompetitorAnalyzeRequest,
    *,
    existing_domains: set[str],
    missing_tiers: list[str] | None = None,
    settings: Settings | None = None,
) -> CompetitorDiscoveryResult:
    """Fetch additional competitors (web search) excluding domains already in the pool."""
    from citationpulse.prompts.competitor_expansion import build_competitor_expansion_messages

    s = settings or get_settings()
    if not openrouter_configured(s):
        raise CompetitorDiscoveryError("OPENROUTER_API_KEY is not configured for competitor expansion.")

    target_domain = registrable_domain(body.target_website)
    if not target_domain:
        raise CompetitorDiscoveryError("Could not parse domain from target_website")

    excluded = set(body.excluded_competitors) | existing_domains
    if target_domain:
        excluded.add(target_domain)

    tiers = [t for t in (missing_tiers or []) if t in ("same_level", "one_level_above")]
    need_same = not tiers or "same_level" in tiers
    need_above = not tiers or "one_level_above" in tiers
    same_cap = EXPANSION_SAME_LEVEL_BATCH if need_same else 0
    above_cap = EXPANSION_ONE_LEVEL_ABOVE_BATCH if need_above else 0
    if same_cap == 0 and above_cap == 0:
        same_cap = EXPANSION_SAME_LEVEL_BATCH
        above_cap = EXPANSION_ONE_LEVEL_ABOVE_BATCH

    messages = build_competitor_expansion_messages(
        target_website=body.target_website,
        competitor_type=body.competitor_type,
        service=body.service,
        niche=body.niche,
        location=body.location,
        excluded_competitors=sorted(excluded),
        market=body.market,
        existing_domains=sorted(existing_domains),
        missing_tiers=tiers or None,
    )

    model = s.competitor_discovery_model or s.chatgpt_model
    try:
        resp = chat_completion_sync(
            model=model,
            messages=messages,
            max_tokens=s.competitor_discovery_max_tokens,
            temperature=0.25,
        )
    except LLMConfigError as exc:
        raise CompetitorDiscoveryError(str(exc)) from exc
    except LLMProviderError as exc:
        raise CompetitorDiscoveryError(f"LLM provider error: {exc}") from exc

    try:
        data = json.loads(_strip_json_payload(resp.text))
    except json.JSONDecodeError as exc:
        raise CompetitorDiscoveryError("Expansion model returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise CompetitorDiscoveryError("Expansion JSON must be an object")

    data = _filter_excluded(data, excluded)
    try:
        return _finalize_discovery(
            data,
            excluded=excluded,
            same_level_cap=same_cap or EXPANSION_SAME_LEVEL_BATCH,
            one_level_above_cap=above_cap or EXPANSION_ONE_LEVEL_ABOVE_BATCH,
        )
    except ValidationError as exc:
        raise CompetitorDiscoveryError(f"Expansion JSON schema error: {exc}") from exc


def _validate_counts(result: CompetitorDiscoveryResult) -> None:
    n_same = len(result.same_level_competitors)
    n_above = len(result.one_level_above_competitors)
    if n_same != SAME_LEVEL_COUNT or n_above != ONE_LEVEL_ABOVE_COUNT:
        raise CompetitorDiscoveryError(
            f"Expected {SAME_LEVEL_COUNT} same-level and {ONE_LEVEL_ABOVE_COUNT} one-level-above "
            f"competitors; got {n_same} and {n_above}. Retry or adjust exclusions."
        )


def analyze_competitors(
    body: CompetitorAnalyzeRequest,
    *,
    settings: Settings | None = None,
) -> CompetitorDiscoveryResult:
    """Run competitor discovery for ``body.target_website``; returns validated JSON shape."""
    s = settings or get_settings()
    if not openrouter_configured(s):
        raise CompetitorDiscoveryError(
            "OPENROUTER_API_KEY is not configured — competitor discovery requires a web-capable model."
        )

    target_domain = registrable_domain(body.target_website)
    if not target_domain:
        raise CompetitorDiscoveryError("Could not parse domain from target_website")

    excluded = set(body.excluded_competitors)
    if target_domain in excluded:
        raise CompetitorDiscoveryError("Target domain cannot appear in excluded_competitors")

    messages = build_competitor_discovery_messages(
        target_website=body.target_website,
        competitor_type=body.competitor_type,
        service=body.service,
        niche=body.niche,
        location=body.location,
        excluded_competitors=list(excluded),
        market=body.market,
    )

    model = s.competitor_discovery_model or s.chatgpt_model
    max_tokens = s.competitor_discovery_max_tokens

    try:
        resp = chat_completion_sync(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.2,
        )
    except LLMConfigError as exc:
        raise CompetitorDiscoveryError(str(exc)) from exc
    except LLMProviderError as exc:
        raise CompetitorDiscoveryError(f"LLM provider error: {exc}") from exc

    try:
        raw_json = _strip_json_payload(resp.text)
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        _log.warning("competitor_discovery: invalid JSON from model: %s", resp.text[:500])
        raise CompetitorDiscoveryError("Model returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise CompetitorDiscoveryError("Model JSON must be an object")

    data = _filter_excluded(data, excluded)

    try:
        result = _finalize_discovery(data, excluded=excluded)
    except ValidationError as exc:
        _log.warning("competitor_discovery: schema validation failed: %s", exc)
        raise CompetitorDiscoveryError(f"Model JSON did not match schema: {exc}") from exc

    return result
