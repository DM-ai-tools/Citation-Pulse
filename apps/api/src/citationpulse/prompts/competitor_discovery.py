"""Competitive intelligence discovery prompt (web-grounded JSON for UI report)."""

from __future__ import annotations

from typing import Literal

from citationpulse.services.competitor_discovery_limits import (
    ONE_LEVEL_ABOVE_COUNT,
    SAME_LEVEL_COUNT,
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
    """Return chat messages for the end-to-end competitor intelligence pipeline."""
    excluded = excluded_competitors or []
    excluded_block = "\n".join(f"- {d}" for d in excluded) if excluded else "(none)"
    ctype_line = (
        competitor_type
        if competitor_type
        else "empty — include both niche_specialist and full_stack_niche"
    )
    service_line = service.strip() if service and service.strip() else "(not provided — infer from website)"
    niche_line = niche.strip() if niche and niche.strip() else "(not provided — do not restrict by niche)"
    location_line = (
        location.strip()
        if location and location.strip()
        else f"(not provided — still focus on {market} nationally)"
    )

    system = (
        "You are an AI-powered competitor intelligence and citation validation engine. "
        "You execute the complete competitor analysis pipeline end-to-end using web search. "
        "You never invent companies, domains, rankings, or metrics. "
        "When data is unavailable, use null in JSON fields. "
        "Return ONLY valid JSON matching the schema in the user message — no markdown, "
        "no code fences, no commentary, no prose outside JSON."
    )

    user = f"""Process the target website through this pipeline in order. Market focus: {market}.

INPUTS
target_website: "{target_website}" (required)
competitor_type: {ctype_line}
service: {service_line}
niche: {niche_line}
location: {location_line}
excluded_competitors (never include):
{excluded_block}

==================================================
1. WEBSITE ANALYSIS
==================================================
Analyze the target URL and determine: primary services, niche/industry, geographic targeting,
business model, SEO maturity, market positioning, authority level, service breadth, company sophistication.

Classify into exactly ONE tier:
Tier 1 → Local Small Specialist
Tier 2 → Established Regional Competitor
Tier 3 → Premium / Multi-City Leader
Tier 4 → National Market Leader

Base tier on: SEO visibility, service structure, authority signals, content sophistication,
geographic reach, business scale.

==================================================
2. COMPETITOR EXTRACTION
==================================================
Identify exactly {SAME_LEVEL_COUNT} SAME-TIER competitors and exactly {ONE_LEVEL_ABOVE_COUNT} ONE-TIER-ABOVE competitors.

Competitors must: operate in the intended market, be true service providers, have strong SEO visibility,
match service intent, match niche intent, match business model, align with targeting filters.

Apply optional filters: competitor_type, service, niche, location, excluded_competitors.

NEVER include: directories, marketplaces, aggregators, inactive sites, irrelevant businesses.

==================================================
3. COMPETITOR VALIDATION
==================================================
For every competitor validate: service similarity, niche similarity, SEO competitiveness,
geographic overlap, business-level similarity.

Same-level = truly comparable. Upper-level = exactly ONE tier stronger (not enterprise outliers).
Remove any competitor that fails prompt constraints.

==================================================
4. CITATION SEARCH & MATCHING
==================================================
For every competitor find evidence from: homepage, service pages, location pages,
ranking/service landing pages, SEO-visible pages, trusted business references.

Every citation must directly support why the competitor was selected (service, niche, geo, SEO, maturity).

==================================================
5. CITATION RELEVANCE SCORING
==================================================
For each citation assign relevance_score (0.0–1.0) based on: exact service match, niche match,
geographic relevance, SEO relevance, authority indicators, business model similarity, source trust, evidence quality.

Remove weak, unsupported, irrelevant, or hallucinated citations.

==================================================
6. CITATION RANKING
==================================================
Order competitors within each list: HIGHEST citation_strength_score → LOWEST.
Order citations within each competitor: MOST relevant → LEAST relevant.
Assign rank (1 = strongest) and rank_reason for each competitor.

citation_strength_score (0.0–1.0) = overall evidence strength for that competitor vs the prompt.

==================================================
7–8. OUTPUT & VALIDATION (before returning JSON)
==================================================
Verify: prompt alignment, exclusions applied, every competitor has ≥1 valid citation with real URLs,
no unsupported SEO claims, no hallucinated companies, correct tier spacing, correct ordering.
If a row fails validation, replace it before finalizing.

==================================================
9. JSON SCHEMA (ONLY output this object)
==================================================

{{
  "target_company": {{
    "domain": "",
    "name": "",
    "detected_services": [],
    "detected_niche": "",
    "detected_locations": [],
    "company_tier": "Tier 1|Tier 2|Tier 3|Tier 4",
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
    {{"type": "homepage|service_page|location_page|about_page|seo_evidence|ranking", "url": "", "evidence": "", "relevance_score": 0.00}}
  ]
}}

Each one_level_above_competitor:
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

RULES: ONLY JSON · exactly {SAME_LEVEL_COUNT} + {ONE_LEVEL_ABOVE_COUNT} competitors · real URLs only · use null for unknown metrics ·
never include excluded domains · prefer strong SEO-visible providers."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
