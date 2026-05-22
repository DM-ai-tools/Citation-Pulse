"""Unit tests for strict 2+2 multi-AI competitor final selection."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.constants.competitor_targets import (  # noqa: E402
    MIN_ENGINE_CITATIONS,
    ONE_LEVEL_ABOVE_COUNT,
    SAME_LEVEL_COUNT,
    TOTAL_COMPETITOR_COUNT,
)
from citationpulse.services.competitor_final_selection import (  # noqa: E402
    evaluate_prompt_block,
    meets_prompt_citation_threshold,
    meets_strict_ai_engine_threshold,
    select_final_competitors,
    strict_requirements_met,
    trim_discovery_json,
    verify_final_competitors,
)


def _row(domain: str, *, level: str, engines: int) -> dict:
    eng_list = [f"e{i}" for i in range(engines)]
    return {
        "domain": domain,
        "name": domain,
        "level": level,
        "engine_count": engines,
        "cited_by_engines": engines > 0,
        "visibility_score": engines * 10.0,
        "citation_count": engines,
        "citations_by_engine": {e: [{"engine": e, "url": f"https://{domain}/"}] for e in eng_list},
        "engine_citations": [{"engine": e, "url": f"https://{domain}/"} for e in eng_list],
        "cited_engines": eng_list,
        "matched_in_discovery": True,
    }


def test_strict_requires_two_engines_not_hit_count_only():
    row = _row("c.com", level="same_level", engines=1)
    row["citation_count"] = 5
    assert meets_prompt_citation_threshold(row, strict_engines_only=True) is False
    assert select_final_competitors([row], {}, allow_tier_fill=False) == []


def test_verify_final_competitors_full_pass():
    selected = [
        _row("s1.com", level="same_level", engines=2),
        _row("s2.com", level="same_level", engines=2),
        _row("u1.com", level="one_level_above", engines=2),
        _row("u2.com", level="one_level_above", engines=2),
    ]
    v = verify_final_competitors(selected)
    assert v["ok"] is True
    assert v["same_level_count"] == SAME_LEVEL_COUNT
    assert v["one_level_above_count"] == ONE_LEVEL_ABOVE_COUNT
    assert v["total_count"] == TOTAL_COMPETITOR_COUNT


def test_strict_requirements_met_all_prompts():
    discovery_map = {
        "s1.com": {"level": "same_level"},
        "s2.com": {"level": "same_level"},
        "u1.com": {"level": "one_level_above"},
        "u2.com": {"level": "one_level_above"},
    }
    block = {
        "prompt_id": "p1",
        "all_ranked_competitors": [
            _row("s1.com", level="same_level", engines=2),
            _row("s2.com", level="same_level", engines=2),
            _row("u1.com", level="one_level_above", engines=2),
            _row("u2.com", level="one_level_above", engines=2),
        ],
    }
    ev = evaluate_prompt_block(block, discovery_map)
    assert ev["verification"]["ok"] is True
    ok, meta = strict_requirements_met({"by_prompt": [block]}, discovery_map)
    assert ok is True
    assert meta["all_requirements_met"] is True


def test_verify_fails_when_short():
    selected = [_row("s1.com", level="same_level", engines=2)]
    v = verify_final_competitors(selected)
    assert v["ok"] is False
    assert v["same_level_count"] == 1
