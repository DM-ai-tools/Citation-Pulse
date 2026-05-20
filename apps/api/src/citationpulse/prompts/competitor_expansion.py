"""Follow-up competitor discovery when tier-balanced engine citations are below minimum."""

from __future__ import annotations

from citationpulse.prompts.competitor_discovery import CompetitorType


def build_competitor_expansion_messages(
    *,
    target_website: str,
    competitor_type: CompetitorType | None = None,
    service: str | None = None,
    niche: str | None = None,
    location: str | None = None,
    excluded_competitors: list[str] | None = None,
    market: str = "Australia",
    existing_domains: list[str] | None = None,
    missing_tiers: list[str] | None = None,
) -> list[dict[str, str]]:
    """Ask the model for additional Australian competitors not already in the pool."""
    excluded = excluded_competitors or []
    excluded_block = "\n".join(f"- {d}" for d in excluded) if excluded else "(none)"
    existing = existing_domains or []
    existing_block = "\n".join(f"- {d}" for d in existing) if existing else "(none)"
    ctype_line = (
        competitor_type
        if competitor_type
        else "missing — include BOTH niche_specialist and full_stack_niche candidates"
    )
    service_line = service.strip() if service and service.strip() else "(infer from target website)"
    niche_line = niche.strip() if niche and niche.strip() else "(no niche restriction)"
    location_line = location.strip() if location and location.strip() else f"(focus on {market})"

    tiers = missing_tiers or []
    tier_focus = ""
    if tiers == ["same_level"]:
        tier_focus = (
            "FOCUS: same-tier competitors only (companies at the SAME company tier as the target). "
            "Use searches like: companies similar to X, best alternatives to X, top competitors of X."
        )
    elif tiers == ["one_level_above"]:
        tier_focus = (
            "FOCUS: one-tier-above competitors only (aspirational / market-leading, exactly ONE tier above target). "
            "Use searches like: enterprise alternatives to X, market leaders in X category, premium providers in X."
        )
    else:
        tier_focus = (
            "Balance output between same-tier (~50%) and one-tier-above (~50%). "
            "Search patterns: companies similar to X, top competitors of X, best alternatives to X, "
            "enterprise alternatives to X, market leaders in X category."
        )

    system = (
        "You are an AI competitor expansion engine for the Australian market. "
        "Use web search, SERPs, comparison articles, and company directories to find "
        "additional real service providers cited in organic search. Return ONLY valid JSON — no markdown."
    )

    user = f"""AI engines (ChatGPT, Claude, Gemini, Perplexity) cited too few competitors for {target_website}.
Find **additional** direct competitors not already listed. The scan will re-check engine citations after you add them.

Target: {target_website}
Market: {market}

service: {service_line}
niche: {niche_line}
location: {location_line}
competitor_type: {ctype_line}

TIER EXPANSION FOCUS:
{tier_focus}

MINIMUM CITED TARGET (after engine re-check):
- at least 2 same-tier competitors cited in ≥1 engine
- at least 2 one-tier-above competitors cited in ≥1 engine
Preferred: up to 3 per tier.

ALREADY TRACKED (must NOT repeat):
{existing_block}

EXCLUDED (must NOT appear):
{excluded_block}

Requirements:
- Use web search / SERP / comparison sources
- Strong SEO-visible Australian providers only
- EXCLUDE directories, marketplaces, aggregators
- Each competitor needs real citation URLs (homepage, service page, ranking evidence)

Output JSON (same schema as initial discovery):
{{
  "target_company": {{ copy from prior analysis or re-infer briefly }},
  "same_level_competitors": [ up to 4 objects if same-tier needed ],
  "one_level_above_competitors": [ up to 4 objects if one-tier-above needed ],
  "validation_summary": {{
    "same_level_validated": 0,
    "one_level_above_validated": 0,
    "citations_verified": true,
    "excluded_domains_removed": true,
    "notes": "expansion batch"
  }}
}}

Each competitor object must include real citation URLs and reasoning (same fields as initial discovery).
ONLY JSON."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
