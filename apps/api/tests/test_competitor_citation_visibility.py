"""Tests for competitor ↔ engine citation matching."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

_VALIDATED_DISCOVERY = {"validation_summary": {"validation_complete": True}}


def _discovery(extra: dict) -> dict:
    return {**extra, **_VALIDATED_DISCOVERY}


from citationpulse.services.competitor_citation_visibility import (  # noqa: E402
    DISPLAY_MAX_COMPETITORS,
    TARGET_ABOVE_TIER_MAX,
    TARGET_SAME_TIER_MAX,
    _collect_engine_citations,
    _count_cited_by_tier,
    _display_cited_competitors,
    _display_user_provided_cited,
    _discovery_competitor_map,
    build_competitor_citation_visibility,
)


def test_discovery_map_and_engine_match():
    discovery = {
        "same_level_competitors": [
            {
                "domain": "flick.com.au",
                "name": "Flick",
                "tier": "Tier 2",
                "rank": 1,
                "citation_strength_score": 0.9,
                "reasoning": "regional",
                "citations": [
                    {
                        "type": "homepage",
                        "url": "https://flick.com.au",
                        "evidence": "National pest control provider.",
                    }
                ],
            }
        ],
        "one_level_above_competitors": [],
    }
    m = _discovery_competitor_map(discovery)
    assert "flick.com.au" in m

    cells = [
        {
            "engine": "chatgpt",
            "citations": [
                {"url": "https://www.flick.com.au/sydney", "ownership": "neutral", "position": 2},
            ],
        },
        {
            "engine": "perplexity",
            "citations": [
                {"url": "https://flick.com.au/", "ownership": "neutral", "position": 1},
            ],
        },
    ]
    by_dom = _collect_engine_citations(cells, engines=["chatgpt", "perplexity"])
    assert "flick.com.au" in by_dom
    assert len(by_dom["flick.com.au"]) == 2


def test_build_visibility_ranks_by_engine_count():
    discovery = {
        "same_level_competitors": [
            {
                "domain": "a.com.au",
                "name": "A",
                "tier": "Tier 2",
                "rank": 1,
                "citation_strength_score": 0.5,
                "reasoning": "a",
                "citations": [],
            },
            {
                "domain": "b.com.au",
                "name": "B",
                "tier": "Tier 2",
                "rank": 2,
                "citation_strength_score": 0.9,
                "reasoning": "b",
                "citations": [],
            },
        ],
        "one_level_above_competitors": [
            {
                "domain": "u1.com.au",
                "name": "U1",
                "tier": "Tier 3",
                "rank": 1,
                "citation_strength_score": 0.8,
                "reasoning": "u1",
                "citations": [],
            },
            {
                "domain": "u2.com.au",
                "name": "U2",
                "tier": "Tier 3",
                "rank": 2,
                "citation_strength_score": 0.7,
                "reasoning": "u2",
                "citations": [],
            },
        ],
        "one_level_above_competitors": [],
    }
    cells = [
        {"engine": "chatgpt", "citations": [{"url": "https://b.com.au", "ownership": "neutral"}]},
        {"engine": "claude", "citations": [{"url": "https://b.com.au", "ownership": "neutral"}]},
        {"engine": "gemini", "citations": [{"url": "https://a.com.au", "ownership": "neutral"}]},
    ]

    class _Scan:
        brand_id = None

    out = build_competitor_citation_visibility(
        None,  # type: ignore[arg-type]
        _Scan(),
        cells=cells,
        engines=["chatgpt", "claude", "gemini"],
        competitor_discovery=discovery,
        prompts=[{"text": "best pest control sydney"}],
    )
    pool = out["all_ranked_competitors"]
    assert pool[0]["domain"] == "b.com.au"
    assert pool[0]["engine_count"] == 2
    assert "citations_by_engine" in pool[0]
    assert len(pool[0]["citations_by_engine"]["chatgpt"]) == 1


def test_build_visibility_by_prompt_filters_cells():
    discovery = _discovery({
        "same_level_competitors": [
            {
                "domain": "hipages.com.au",
                "name": "hipages",
                "tier": "Tier 2",
                "rank": 1,
                "citation_strength_score": 0.8,
                "reasoning": "marketplace",
                "citations": [],
            }
        ],
        "one_level_above_competitors": [],
    })
    p1, p2 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    cells = [
        {
            "promptId": p1,
            "engine": "chatgpt",
            "citations": [{"url": "https://hipages.com.au", "ownership": "neutral", "position": 1}],
        },
        {
            "promptId": p2,
            "engine": "chatgpt",
            "citations": [],
        },
    ]

    class _Scan:
        brand_id = None

    out = build_competitor_citation_visibility(
        None,  # type: ignore[arg-type]
        _Scan(),
        cells=cells,
        engines=["chatgpt"],
        competitor_discovery=discovery,
        prompts=[
            {"id": p1, "text": "hipages vs Airtasker"},
            {"id": p2, "text": "best tradies app"},
        ],
    )
    by_prompt = out.get("by_prompt") or []
    assert len(by_prompt) == 2
    p1_vis = next(x for x in by_prompt if x["prompt_id"] == p1)
    p2_vis = next(x for x in by_prompt if x["prompt_id"] == p2)
    assert p1_vis["total_cited_pool"] == 1
    assert p2_vis["total_cited_pool"] == 0


def test_user_provided_competitors_included():
    discovery = {
        "same_level_competitors": [
            {
                "domain": "discovered.com.au",
                "name": "Discovered Co",
                "tier": "Tier 2",
                "rank": 1,
                "citation_strength_score": 0.7,
                "reasoning": "ai",
                "citations": [],
            }
        ],
        "one_level_above_competitors": [],
    }

    from citationpulse.models.domain import Brand

    class _MainBrand:
        competitors = ["user-brand-id"]

    class _UserBrand:
        name = "Airtasker"
        domains = ["airtasker.com"]
        tenant_id = None

    class _Scan:
        brand_id = "brand-1"
        id = "scan-test-id"

    class _Db:
        def get(self, model, pk):
            if model is Brand and pk == "brand-1":
                return _MainBrand()
            if model is Brand and pk == "user-brand-id":
                return _UserBrand()
            return None

        def scalars(self, _stmt):
            class _Rows:
                def all(self):
                    return []

            return _Rows()

    out = build_competitor_citation_visibility(
        _Db(),  # type: ignore[arg-type]
        _Scan(),  # type: ignore[arg-type]
        cells=[],
        engines=["chatgpt"],
        competitor_discovery=discovery,
        prompts=[],
    )
    all_domains = {r["domain"] for r in out.get("all_ranked_competitors", [])}
    assert "discovered.com.au" in all_domains
    assert "airtasker.com" in all_domains
    assert out["user_provided_count"] >= 1
    # Uncited competitors are excluded from per-prompt display (rules 5–6).
    assert out["ranked_competitors"] == []
    assert len(out["discovery_only"]) >= 1


def _two_engine_row(**kwargs: object) -> dict:
    base = dict(kwargs)
    base.setdefault("cited_by_engines", True)
    base.setdefault("engines", ["chatgpt", "claude"])
    base.setdefault("cited_engines", ["chatgpt", "claude"])
    base.setdefault("engine_count", 2)
    base.setdefault("citation_count", 2)
    dom = str(base.get("domain", "x.com.au"))
    base.setdefault(
        "citations_by_engine",
        {
            "chatgpt": [{"url": f"https://{dom}", "position": 1}],
            "claude": [{"url": f"https://{dom}/about", "position": 2}],
        },
    )
    return base


def test_display_cited_tier_balanced_caps():
    ranked = []
    for i in range(5):
        ranked.append(
            _two_engine_row(
                domain=f"same{i}.com.au",
                name=f"S{i}",
                level="same_level",
                visibility_score=90 - i,
            )
        )
    for i in range(5):
        ranked.append(
            _two_engine_row(
                domain=f"above{i}.com.au",
                name=f"A{i}",
                level="one_level_above",
                visibility_score=80 - i,
            )
        )
    display = _display_cited_competitors(ranked)
    assert len(display) == DISPLAY_MAX_COMPETITORS
    same, above = _count_cited_by_tier(display)
    assert same == TARGET_SAME_TIER_MAX
    assert above == TARGET_ABOVE_TIER_MAX
    assert all(r.get("cited_engines_detail") for r in display)


def test_display_user_provided_cited_any_engine():
    ranked = [
        {
            "domain": "userco.com.au",
            "name": "User Co",
            "level": "user_provided",
            "user_provided": True,
            "cited_by_engines": True,
            "engines": ["chatgpt"],
            "cited_engines": ["chatgpt"],
            "engine_count": 1,
            "citation_count": 1,
            "citations_by_engine": {"chatgpt": [{"url": "https://userco.com.au", "position": 1}]},
            "engine_citations": [],
        },
        {
            "domain": "other.com.au",
            "name": "Other",
            "level": "same_level",
            "user_provided": False,
            "cited_by_engines": True,
            "engines": ["chatgpt", "claude"],
            "cited_engines": ["chatgpt", "claude"],
            "engine_count": 2,
            "citation_count": 2,
            "citations_by_engine": {
                "chatgpt": [{"url": "https://other.com.au"}],
                "claude": [{"url": "https://other.com.au/about"}],
            },
            "engine_citations": [],
        },
    ]
    display = _display_user_provided_cited(ranked)
    assert len(display) == 1
    assert display[0]["domain"] == "userco.com.au"


def test_display_cited_excludes_uncited_and_balances_tiers():
    ranked = [
        {
            "domain": f"c{i}.com.au",
            "name": f"C{i}",
            "level": "same_level" if i < 4 else "one_level_above",
            "visibility_score": 90 - i,
            "visibility_rank": i + 1,
            "cited_by_engines": i != 3,
            "engines": ["chatgpt"] if i != 3 else [],
            "cited_engines": ["chatgpt"] if i != 3 else [],
            "engine_count": 0 if i == 3 else 1,
            "citation_count": 0 if i == 3 else 1,
            "citations_by_engine": {"chatgpt": [{"url": f"https://c{i}.com.au"}]} if i != 3 else {},
            "engine_citations": [],
        }
        for i in range(7)
    ]
    display = _display_cited_competitors(ranked)
    assert len(display) <= DISPLAY_MAX_COMPETITORS
    assert all(r["cited_by_engines"] for r in display)
    assert "c3.com.au" not in {r["domain"] for r in display}
    same, above = _count_cited_by_tier(display)
    assert same <= TARGET_SAME_TIER_MAX
    assert above <= TARGET_ABOVE_TIER_MAX


def test_collect_tracked_domain_citations_without_competitor_tag():
    cells = [
        {
            "promptId": "p1",
            "engine": "chatgpt",
            "citations": [
                {"url": "https://airtasker.com/jobs", "ownership": "neutral"},
                {"url": "https://random.org/", "ownership": "neutral"},
            ],
        },
    ]
    by_dom = _collect_engine_citations(
        cells,
        engines=["chatgpt"],
        prompt_id="p1",
        competitors_only=True,
        tracked_competitor_domains={"airtasker.com"},
    )
    assert "airtasker.com" in by_dom
    assert "random.org" not in by_dom
