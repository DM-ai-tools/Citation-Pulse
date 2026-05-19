"""Competitive intelligence discovery prompt (Australian market, JSON-only output)."""

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
    """Return OpenRouter chat messages (system + user) for competitor analysis."""
    excluded = excluded_competitors or []
    excluded_block = (
        "\n".join(f"- {d}" for d in excluded)
        if excluded
        else "(none)"
    )
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
        else "(not provided — still focus on Australia nationally)"
    )

    system = (
        "You are an expert competitive intelligence and market positioning analyst. "
        "You use web search to verify real businesses, pages, and SEO signals. "
        "You never invent companies, domains, rankings, or metrics. "
        "When data is unavailable, use null in JSON fields. "
        "Return ONLY valid JSON matching the schema in the user message — no markdown, "
        "no code fences, no commentary."
    )

    user = f"""Analyze the user-provided company website and identify:
1. The company's market level/tier
2. Exactly 3 direct competitors on the SAME tier/level
3. Exactly 3 competitors ONE tier ABOVE the company
4. Supporting citations/sources for all findings

The analysis must focus on the {market} market unless otherwise specified.

INPUTS

target_website: "{target_website}" (required)

Optional Inputs:
competitor_type:
- "niche_specialist"
- "full_stack_niche"
- empty = include both
→ Applied: {ctype_line}

service:
- specific service the competitors must offer
→ Applied: {service_line}

niche:
- target industry/niche
→ Applied: {niche_line}

location:
- city/state/region in {market}
→ Applied: {location_line}

excluded_competitors:
- list of domains to exclude completely
→ Applied:
{excluded_block}

==================================================
STEP 1 — ANALYZE THE TARGET COMPANY
==================================================

Analyze the target website and determine:

- Primary services
- Industry niche
- Geographic targeting
- SEO strength
- Market positioning
- Business model
- Company sophistication level

Then classify the company into ONE of these tiers:

Tier 1 → Local Small Specialist
- Small/local operator
- Limited service area
- Lower SEO authority
- Few service pages

Tier 2 → Established Regional Competitor
- Strong regional presence
- Multiple optimized service pages
- Consistent rankings
- Moderate authority

Tier 3 → Premium / Multi-City Leader
- Strong brand visibility
- High SEO authority
- Multi-location or statewide presence
- Strong content strategy

Tier 4 → National Market Leader
- National presence
- Dominant SEO visibility
- Large-scale operations
- Strong authority and backlinks

==================================================
COMPETITOR DISTRIBUTION RULES
==================================================

You MUST return:
- Exactly {SAME_LEVEL_COUNT} competitors from the SAME company tier/level
- Exactly {ONE_LEVEL_ABOVE_COUNT} competitors from ONE LEVEL ABOVE the target company

Do NOT return more or fewer competitors.

==================================================
STEP 2 — FIND COMPETITORS
==================================================

Find exactly {SAME_LEVEL_COUNT} SAME-LEVEL and exactly {ONE_LEVEL_ABOVE_COUNT} ONE-LEVEL-ABOVE competitors.

Competitors must:
- Operate in {market}
- Be true service providers
- Have strong organic visibility
- Rank well for relevant services
- Match the business model
- Match service/niche relevance when provided

STRICTLY EXCLUDE:
- Directories
- Aggregators
- Marketplaces
- Inactive websites
- Low-authority sites

If service is provided:
- prioritize exact service match

If niche is provided:
- prioritize niche alignment

If location is provided:
- boost local competitors

If competitor_type is provided:
- enforce filtering

==================================================
STEP 3 — COMPETITOR LEVEL MATCHING
==================================================

SAME-LEVEL competitors (exactly {SAME_LEVEL_COUNT}):
These competitors must closely match the target company in:
- SEO authority
- Geographic reach
- Service breadth
- Brand maturity
- Business size
- Organic visibility

Examples:
- Local specialist vs local specialist
- Regional provider vs regional provider

UPPER-LEVEL competitors (exactly {ONE_LEVEL_ABOVE_COUNT}):
These competitors must be exactly ONE tier stronger than the target company.

They should demonstrate:
- Stronger SEO authority
- Larger market reach
- Better rankings
- More sophisticated service/content structure
- Higher perceived market position

Do NOT include:
- Massive enterprise brands if the gap is too large
- Companies more than one tier above

==================================================
STEP 4 — CITATIONS & EVIDENCE
==================================================

For EVERY competitor include:
- Homepage URL
- Evidence URLs
- Ranking/service page URLs
- Citation snippets showing why they qualify

Citations should support:
- service relevance
- niche relevance
- SEO visibility
- geographic targeting
- company scale

==================================================
STEP 5 — OUTPUT FORMAT
==================================================

Return ONLY valid JSON.

Structure:

{{
  "target_company": {{
    "domain": "",
    "name": "",
    "detected_services": [],
    "detected_niche": "",
    "detected_locations": [],
    "company_tier": "",
    "tier_reasoning": ""
  }},
  "same_level_competitors": [{SAME_LEVEL_COUNT} items exactly — each with domain, name, tier, similarity_score, avg_position, intersections, reasoning, citations],
  "one_level_above_competitors": [{ONE_LEVEL_ABOVE_COUNT} items exactly — each with domain, name, tier, authority_advantage, reasoning, citations]
}}

Each same_level_competitor object:
{{
  "domain": "",
  "name": "",
  "tier": "",
  "similarity_score": 0.00,
  "avg_position": null,
  "intersections": null,
  "reasoning": "",
  "citations": [{{"type": "homepage|service_page|about_page|seo_evidence|ranking", "url": "", "evidence": ""}}]
}}

Each one_level_above_competitor object:
{{
  "domain": "",
  "name": "",
  "tier": "",
  "authority_advantage": "",
  "reasoning": "",
  "citations": [{{"type": "homepage|service_page|about_page|seo_evidence|ranking", "url": "", "evidence": ""}}]
}}

==================================================
IMPORTANT RULES
==================================================

- Return ONLY JSON
- No markdown
- No explanations
- No commentary
- No extra text
- Exactly {SAME_LEVEL_COUNT} same_level_competitors
- Exactly {ONE_LEVEL_ABOVE_COUNT} one_level_above_competitors
- Use null where data is unavailable
- Never include excluded competitors
- Prefer companies with strong SEO visibility
- Use real evidence/citations only
- Do not hallucinate metrics
- If metrics are unavailable, use null
"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
