"""Unit tests for competitor discovery prompt + JSON parsing (no live LLM)."""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.prompts.competitor_discovery import build_competitor_discovery_messages  # noqa: E402
from citationpulse.schemas.competitors import CompetitorAnalyzeRequest, CompetitorDiscoveryResult  # noqa: E402
from citationpulse.services.competitor_discovery import (  # noqa: E402
    SAME_LEVEL_COUNT,
    ONE_LEVEL_ABOVE_COUNT,
    CompetitorDiscoveryError,
    _filter_excluded,
    _finalize_discovery,
    _strip_json_payload,
    _validate_counts,
)


def test_build_messages_includes_target_and_exclusions():
    msgs = build_competitor_discovery_messages(
        target_website="https://example.com.au",
        service="gutter replacement",
        niche="residential roofing",
        location="Melbourne",
        competitor_type="niche_specialist",
        excluded_competitors=["yellowpages.com.au"],
    )
    assert len(msgs) == 2
    user = msgs[1]["content"]
    assert "https://example.com.au" in user
    assert "gutter replacement" in user
    assert "yellowpages.com.au" in user
    assert "exactly 5 objects" in user
    assert "5 same_level_competitors" in user
    assert "validation_summary" in user


def test_strip_json_payload_removes_fence():
    raw = '```json\n{"target_company": {}}\n```'
    assert _strip_json_payload(raw).startswith("{")


def test_filter_excluded_removes_domains():
    payload = {
        "target_company": {"domain": "target.com.au", "name": "T"},
        "same_level_competitors": [
            {"domain": "keep.com.au", "name": "K"},
            {"domain": "drop.com.au", "name": "D"},
        ],
        "one_level_above_competitors": [],
    }
    out = _filter_excluded(payload, {"drop.com.au"})
    assert len(out["same_level_competitors"]) == 1
    assert out["same_level_competitors"][0]["domain"] == "keep.com.au"


def test_validate_counts_raises():
    sample = {
        "target_company": {
            "domain": "x.com",
            "name": "X",
            "detected_services": [],
            "detected_niche": "",
            "detected_locations": [],
            "company_tier": "Tier 1",
            "tier_reasoning": "r",
        },
        "same_level_competitors": [],
        "one_level_above_competitors": [],
    }
    result = CompetitorDiscoveryResult.model_validate(sample)
    with pytest.raises(CompetitorDiscoveryError):
        _validate_counts(result)


def test_request_normalizes_website_and_excluded():
    req = CompetitorAnalyzeRequest(
        target_website="www.example.com.au",
        excluded_competitors=["https://www.bad.com/path"],
    )
    assert req.target_website.startswith("https://")
    assert "bad.com" in req.excluded_competitors


def _sample_result_dict() -> dict:
    same = [
        {
            "domain": f"c{i}.com.au",
            "name": f"C{i}",
            "tier": "Tier 2",
            "similarity_score": 0.8,
            "avg_position": None,
            "intersections": None,
            "reasoning": "match",
            "citations": [
                {
                    "type": "homepage",
                    "url": f"https://c{i}.com.au",
                    "evidence": "Service pages and local SEO footprint match the target.",
                    "relevance_score": 0.85,
                }
            ],
        }
        for i in range(SAME_LEVEL_COUNT)
    ]
    above = [
        {
            "domain": f"u{i}.com.au",
            "name": f"U{i}",
            "tier": "Tier 3",
            "authority_advantage": "stronger",
            "reasoning": "above",
            "citations": [
                {
                    "type": "homepage",
                    "url": f"https://u{i}.com.au",
                    "evidence": "Stronger regional SEO authority and broader service coverage.",
                    "relevance_score": 0.9,
                }
            ],
        }
        for i in range(ONE_LEVEL_ABOVE_COUNT)
    ]
    return {
        "target_company": {
            "domain": "target.com.au",
            "name": "Target",
            "detected_services": ["gutters"],
            "detected_niche": "roofing",
            "detected_locations": ["Melbourne"],
            "company_tier": "Tier 2",
            "tier_reasoning": "regional",
        },
        "same_level_competitors": same,
        "one_level_above_competitors": above,
    }


def test_full_schema_roundtrip():
    data = _sample_result_dict()
    parsed = CompetitorDiscoveryResult.model_validate(data)
    _validate_counts(parsed)
    dumped = json.loads(parsed.model_dump_json())
    assert len(dumped["same_level_competitors"]) == SAME_LEVEL_COUNT
    assert len(dumped["one_level_above_competitors"]) == ONE_LEVEL_ABOVE_COUNT


def test_finalize_discovery_assigns_ranks():
    result = _finalize_discovery(_sample_result_dict(), excluded=set())
    assert result.same_level_competitors[0].rank == 1
    assert result.same_level_competitors[0].citation_strength_score is not None
    assert result.validation_summary is not None
    assert result.validation_summary.citations_verified is True


def test_blocked_domain_rejected():
    from citationpulse.services.competitor_discovery import _normalize_same_row

    row = {
        "domain": "yellowpages.com.au",
        "name": "YP",
        "tier": "Tier 2",
        "similarity_score": 0.9,
        "reasoning": "bad",
        "citations": [
            {
                "type": "homepage",
                "url": "https://yellowpages.com.au/x",
                "evidence": "directory listing only",
            }
        ],
    }
    assert _normalize_same_row(row, target_tier=2) is None
