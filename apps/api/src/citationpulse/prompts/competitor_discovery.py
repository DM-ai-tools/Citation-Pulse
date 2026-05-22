"""Competitive intelligence discovery prompt (web-grounded JSON for UI report)."""

from __future__ import annotations

from typing import Literal

from citationpulse.constants.competitor_targets import (
    MIN_ENGINE_CITATIONS,
    ONE_LEVEL_ABOVE_COUNT,
    SAME_LEVEL_COUNT,
    TOTAL_COMPETITOR_COUNT,
)

CompetitorType = Literal["niche_specialist", "full_stack_niche"]


def build_competitor_discovery_messages(
    *,
    target_website: str,
    competitor_type: CompetitorType | None = None,
    service: str | None = None,
    niche: str | None = None,
    location: str | None = None,
    excluded_competitors: list[str] | None = None,
    market: str = "Australia",
) -> list[dict[str, str]]:
    """Return chat messages for Australian direct-competitor discovery (tiered JSON for the app)."""
    initial_total = SAME_LEVEL_COUNT + ONE_LEVEL_ABOVE_COUNT
    excluded = excluded_competitors or []
    excluded_block = "\n".join(f"- {d}" for d in excluded) if excluded else "(none)"
    ctype_line = (
        competitor_type
        if competitor_type
        else "missing or empty — include BOTH niche_specialist and full_stack_niche candidates"
    )
    service_line = service.strip() if service and service.strip() else "(missing — infer core services from the target website)"
    niche_line = niche.strip() if niche and niche.strip() else "(missing — do not restrict by niche)"
    location_line = (
        location.strip()
        if location and location.strip()
        else f"(missing — still focus on {market} nationally; rank local leaders higher when geo signals exist on-site)"
    )

    system = (
        "You are an AI-powered competitor intelligence engine for the Australian market. "
        "Use web search to find real, SEO-visible service providers — never invent companies, domains, "
        "rankings, or metrics. When data is unavailable, use null in JSON fields. "
        "Return ONLY valid JSON matching the schema in the user message — no markdown, "
        "no code fences, no commentary, no prose outside JSON."
    )

    user = f"""Find direct competitors in the {market} market for the company at:
{target_website}

Use the optional targeting inputs below to control how narrow or broad the competitor set should be.

==================================================
ADDITIONAL INPUTS (all optional unless stated)
==================================================

competitor_type: {ctype_line}

Expected values:
- "niche_specialist" = specialized in a particular niche/industry and its services
- "full_stack_niche" = full-service company offering multiple services but clearly targeted to one niche/industry
If missing or empty, include both types in your research pool.

service: {service_line}

A single service the user wants competitors for (e.g. "gutter replacement", "roof plumbing").
If missing/empty, infer core services from the target domain.

IMPORTANT: If service is "webinar", ONLY include companies that explicitly use webinars as lead magnets,
offers, or educational resources.

niche: {niche_line}

Industry/niche (e.g. "residential roofing", "gutter replacement"). If missing/empty, do not restrict by niche.

location: {location_line}

City/region/state (e.g. "Melbourne", "Sydney NSW"). If provided, prioritize competitors based in or
explicitly serving this location; rank local leaders higher.

excluded_competitors (MUST NOT appear in output):
{excluded_block}

==================================================
COMPETITOR SELECTION LOGIC (internal research — then output {SAME_LEVEL_COUNT}+{ONE_LEVEL_ABOVE_COUNT})
==================================================

Research at least 8–10 strong Australian direct competitors internally, then select the best {initial_total} for output.

IF BOTH service AND niche are provided:
- Companies in {market} that offer the specified service AND clearly target the specified niche
- Apply competitor_type filter if provided
- Exclude generalists without niche alignment
- MUST have strong organic visibility (ranking pages, consistent SEO presence)

IF ONLY service is provided:
- Strong {market} competitors that prominently offer the specified service
- No niche restriction required
- Prioritize strong SEO presence and organic traffic
- Boost local relevance if location is provided

IF service is missing/empty:
- Infer services from {target_website}
- Find direct competitors offering similar services in {market}
- Match business model (local service provider, contractor, or specialist)
- Filter by competitor_type if provided

CRITICAL REQUIREMENTS (all candidates):
- ONLY high-quality competitors with strong organic traffic and SEO presence in {market}
- Prefer companies that rank well on Google for relevant keywords, have optimized service pages,
  and show consistent search visibility
- EXCLUDE: directories (Yellow Pages, Yelp, True Local, Hipages, OneFlare, etc.), marketplaces,
  aggregators, low-quality or inactive sites
- Competitors must be true service providers, not aggregators

==================================================
TIER CLASSIFICATION (target + each competitor)
==================================================

Classify the target and each selected competitor into exactly ONE tier:
- Tier 1 → Local Small Specialist
- Tier 2 → Established Regional Competitor
- Tier 3 → Premium / Multi-City Leader
- Tier 4 → National Market Leader
- Tier 5 → Enterprise / Global Category Leader (use when clearly above national scale)
- Tier 6 → Platform / Conglomerate Leader (rare; only when evidence supports it)

==================================================
OUTPUT COMPETITOR SET (project schema — NOT a flat array)
==================================================

From your research pool, output:
- Exactly {SAME_LEVEL_COUNT} competitors from the SAME company tier as the target → same_level_competitors
- Exactly {ONE_LEVEL_ABOVE_COUNT} competitors ahead of the target (one company tier up) → one_level_above_competitors
({initial_total} total; ~50% same-tier, ~50% competitors ahead; prefer one tier step up, but if the target is Tier 4+ pick the next tier up to Tier 6 when real market leaders exist.)

For each competitor provide citations (real URLs) supporting selection: homepage, service_page,
location_page, about_page, seo_evidence, or ranking pages.

==================================================
SCORING GUIDANCE
==================================================

similarity_score (0.0–1.0) for same-level rows:
- Service match (highest weight if service provided)
- Niche match (highest weight if niche provided)
- Business model similarity (local contractor vs agency vs specialist)
- Geographic relevance (boost if location provided)
- Organic search competitiveness overlap

citation_strength_score (0.0–1.0): overall evidence strength vs the prompt.
relevance_score (0.0–1.0) per citation. Use null for avg_position or intersections if unknown.

Rank competitors strongest-first within each list (rank 1 = best).

IMPORTANT: Return ONLY {TOTAL_COMPETITOR_COUNT} competitors total ({SAME_LEVEL_COUNT} same-tier + {ONE_LEVEL_ABOVE_COUNT} competitors ahead).
Do not include spare or alternate competitors in the JSON.

==================================================
JSON SCHEMA (ONLY output this object)
==================================================

{{
  "target_company": {{
    "domain": "",
    "name": "",
    "detected_services": [],
    "detected_niche": "",
    "detected_locations": [],
    "company_tier": "Tier 1|Tier 2|Tier 3|Tier 4|Tier 5|Tier 6",
    "tier_reasoning": ""
  }},
  "same_level_competitors": [ exactly {SAME_LEVEL_COUNT} objects, ordered strongest-first ],
  "one_level_above_competitors": [ exactly {ONE_LEVEL_ABOVE_COUNT} objects, ordered strongest-first ],
  "validation_summary": {{
    "same_level_validated": {SAME_LEVEL_COUNT},
    "one_level_above_validated": {ONE_LEVEL_ABOVE_COUNT},
    "citations_verified": true,
    "excluded_domains_removed": true,
    "notes": ""
  }}
}}

Each same_level_competitor:
{{
  "domain": "",
  "name": "",
  "tier": "Tier N",
  "rank": 1,
  "rank_reason": "",
  "similarity_score": 0.00,
  "citation_strength_score": 0.00,
  "avg_position": null,
  "intersections": null,
  "reasoning": "",
  "citations": [
    {{"type": "homepage|service_page|location_page|about_page|seo_evidence|ranking",
      "url": "", "evidence": "", "relevance_score": 0.00}}
  ]
}}

Each competitors-ahead row (one_level_above_competitor):
{{
  "domain": "",
  "name": "",
  "tier": "Tier N",
  "rank": 1,
  "rank_reason": "",
  "citation_strength_score": 0.00,
  "authority_advantage": "",
  "reasoning": "",
  "citations": [ same citation shape as above ]
}}

RULES:
- ONLY JSON · exactly {SAME_LEVEL_COUNT} same_level_competitors · exactly {ONE_LEVEL_ABOVE_COUNT} one_level_above_competitors
- real URLs only · null for unknown metrics · never include excluded domains
- prefer strong SEO-visible Australian providers"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
