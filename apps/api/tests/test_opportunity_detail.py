"""Tests for expandable gap detail copy."""

from uuid import uuid4

from citationpulse.services.opportunity_detail import (
    OpportunityDetailContext,
    build_deterministic_detail,
)


def test_build_deterministic_detail_engine_specific():
    ctx = OpportunityDetailContext(
        opportunity_id=uuid4(),
        brand_id=uuid4(),
        brand_name="Hipages",
        prompt_text="best plumber Sydney",
        gap_type="engine_specific_gap",
        scope="claude",
        grade="C",
        heat="COOL",
        description="Cited on 3 engines but absent from Claude",
        est_volume=1200,
        engine_states={
            "chatgpt": "CITED_TOP",
            "claude": "MISSING",
            "gemini": "CITED_LOWER",
            "perplexity": "CITED_TOP",
        },
        top_competitor="oneflare.com",
        consecutive_gap_runs=2,
    )
    text = build_deterministic_detail(ctx)
    assert "Claude" in text
    assert "oneflare" in text
    assert len(text) > 40
