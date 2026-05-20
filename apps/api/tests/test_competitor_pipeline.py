"""Unit tests for competitor citation expansion pipeline (no live LLM)."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.services.competitor_citation_visibility import (  # noqa: E402
    TARGET_ABOVE_TIER_MIN,
    TARGET_SAME_TIER_MIN,
    tier_balance_shortfall_for_visibility,
)


def _cited_row(domain: str, *, level: str) -> dict:
    return {
        "domain": domain,
        "cited_by_engines": True,
        "level": level,
        "citations_by_engine": {"chatgpt": [{"url": f"https://{domain}", "position": 1}]},
        "engines": ["chatgpt"],
        "cited_engines": ["chatgpt"],
    }


def test_tier_shortfall_when_same_tier_under_minimum():
    vis = {
        "all_ranked_competitors": [
            _cited_row("a.com.au", level="same_level"),
            _cited_row("b.com.au", level="one_level_above"),
            _cited_row("c.com.au", level="one_level_above"),
        ],
        "tier_balance": {
            "same_tier_cited": 1,
            "one_above_tier_cited": 2,
            "missing_tiers": ["same_level"],
        },
    }
    assert tier_balance_shortfall_for_visibility(vis) == ["__aggregate__"]


def test_tier_shortfall_empty_when_minimums_met():
    rows = [
        _cited_row("a.com.au", level="same_level"),
        _cited_row("b.com.au", level="same_level"),
        _cited_row("c.com.au", level="one_level_above"),
        _cited_row("d.com.au", level="one_level_above"),
    ]
    vis = {"all_ranked_competitors": rows}
    assert tier_balance_shortfall_for_visibility(vis) == []
    assert TARGET_SAME_TIER_MIN == 2
    assert TARGET_ABOVE_TIER_MIN == 2


def test_tier_shortfall_per_prompt():
    p1, p2 = "p1", "p2"
    vis = {
        "by_prompt": [
            {
                "prompt_id": p1,
                "all_ranked_competitors": [
                    _cited_row("a.com.au", level="same_level"),
                    _cited_row("b.com.au", level="same_level"),
                    _cited_row("c.com.au", level="one_level_above"),
                    _cited_row("d.com.au", level="one_level_above"),
                ],
            },
            {
                "prompt_id": p2,
                "all_ranked_competitors": [
                    _cited_row("only.com.au", level="same_level"),
                ],
            },
        ]
    }
    short = tier_balance_shortfall_for_visibility(vis)
    assert short == [p2]
