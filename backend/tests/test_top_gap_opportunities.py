"""Unit tests for the Top Gap Opportunities pipeline.

Covers:
  * classify_gap rule priority + scope selection
  * opportunity_score with demand_bucket=high absent_all floor
  * demand decomposition + bucket / score helpers
  * 4-step resolve_demand fallback (with monkeypatched DataForSEO)
  * Redis cache wrapper falls back to in-process when REDIS_URL is unset

These are pure-Python tests — no DB needed for the helpers. The resolver
tests use a tiny FakeSession that mimics the parts of sqlalchemy Session
we touch, so the file runs in any pytest environment.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

# Make ``backend/src`` importable when running ``pytest`` from repo root.
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.services import cache  # noqa: E402
from citationpulse.services.demand import (  # noqa: E402
    DEFAULT_DEMAND_BUCKET,
    DEFAULT_DEMAND_SCORE,
    DemandResult,
    bucket_from_volume,
    decompose_prompt,
    normalise,
    resolve_demand,
    score_from_volume,
)
from citationpulse.services.opportunities import (  # noqa: E402
    CITED_LOWER,
    CITED_TOP,
    COMPETITOR_ONLY,
    MISSING,
    classify_gap,
    demand_pill_from_bucket,
    grade_from_score,
    opportunity_score,
)


# ---------------------------------------------------------------------------
# classify_gap
# ---------------------------------------------------------------------------
ENGINES = ["chatgpt", "claude", "gemini", "perplexity"]


def test_classify_absent_all():
    latest = {e: MISSING for e in ENGINES}
    assert classify_gap(latest, {}, ENGINES) == ("absent_all", None)


def test_classify_competitor_dominant_requires_two_engines():
    latest = {
        "chatgpt": COMPETITOR_ONLY,
        "claude": COMPETITOR_ONLY,
        "gemini": MISSING,
        "perplexity": MISSING,
    }
    assert classify_gap(latest, {}, ENGINES) == ("competitor_dominant", None)


def test_classify_engine_specific_gap_picks_missing_engine():
    latest = {
        "chatgpt": CITED_TOP,
        "claude": CITED_TOP,
        "gemini": CITED_LOWER,
        "perplexity": MISSING,
    }
    result = classify_gap(latest, {}, ENGINES)
    assert result == ("engine_specific_gap", "perplexity")


def test_classify_weak_engine_when_three_cited_plus_competitor_only():
    latest = {
        "chatgpt": CITED_TOP,
        "claude": CITED_TOP,
        "gemini": CITED_LOWER,
        "perplexity": COMPETITOR_ONLY,
    }
    result = classify_gap(latest, {}, ENGINES)
    assert result == ("weak_engine", "perplexity")


def test_classify_refresh_content_when_prev_cited_now_competitor_only():
    latest = {
        "chatgpt": COMPETITOR_ONLY,
        "claude": MISSING,
        "gemini": MISSING,
        "perplexity": MISSING,
    }
    prev = {"chatgpt": CITED_TOP}
    # Not competitor_dominant (only 1 comp), not weak_engine (no >=3 cited),
    # so it should fall through to refresh_content via prev state.
    result = classify_gap(latest, prev, ENGINES)
    assert result == ("refresh_content", "chatgpt")


def test_classify_returns_none_when_brand_strong_everywhere():
    latest = {e: CITED_TOP for e in ENGINES}
    assert classify_gap(latest, {}, ENGINES) is None


# ---------------------------------------------------------------------------
# opportunity_score
# ---------------------------------------------------------------------------
def test_opportunity_score_uses_demand_score_when_provided():
    latest = {e: MISSING for e in ENGINES}
    s = opportunity_score(
        est_volume=None,
        latest_states=latest,
        gap_type="absent_all",
        competitor_cites=0,
        consecutive_gap_runs=0,
        demand_score=0.9,
        demand_bucket="high",
    )
    # demand 0.9 * 0.4 + gap 1.0 * 0.3 = 0.66, but the high-bucket floor lifts to 0.71.
    assert s >= 0.71
    assert grade_from_score(s) == "A"


def test_absent_all_high_bucket_forces_grade_a_even_with_weak_signal():
    latest = {e: MISSING for e in ENGINES}
    s = opportunity_score(
        est_volume=None,
        latest_states=latest,
        gap_type="absent_all",
        competitor_cites=0,
        consecutive_gap_runs=0,
        demand_score=0.05,
        demand_bucket="high",
    )
    assert s >= 0.71
    assert grade_from_score(s) == "A"


def test_absent_all_low_bucket_does_not_force_floor():
    latest = {e: MISSING for e in ENGINES}
    s = opportunity_score(
        est_volume=None,
        latest_states=latest,
        gap_type="absent_all",
        competitor_cites=0,
        consecutive_gap_runs=0,
        demand_score=0.05,
        demand_bucket="low",
    )
    assert s < 0.71


def test_grade_thresholds():
    assert grade_from_score(0.71) == "A"
    assert grade_from_score(0.70) == "A"
    assert grade_from_score(0.69) == "B"
    assert grade_from_score(0.40) == "B"
    assert grade_from_score(0.39) == "C"


def test_demand_pill_from_bucket_handles_unknowns():
    assert demand_pill_from_bucket("high") == "HIGH"
    assert demand_pill_from_bucket("medium") == "MEDIUM"
    assert demand_pill_from_bucket("low") == "LOW"
    assert demand_pill_from_bucket(None) == "UNKNOWN"
    assert demand_pill_from_bucket("garbage") == "UNKNOWN"


# ---------------------------------------------------------------------------
# Demand helpers
# ---------------------------------------------------------------------------
def test_normalise_strips_punctuation_and_lowercases():
    assert normalise("Best CRM for SMB? Or, alternatives!!") == "best crm for smb or alternatives"


def test_bucket_thresholds():
    assert bucket_from_volume(None) == "unknown"
    assert bucket_from_volume(0) == "unknown"
    assert bucket_from_volume(49) == "low"
    assert bucket_from_volume(499) == "low"
    assert bucket_from_volume(500) == "medium"
    assert bucket_from_volume(4999) == "medium"
    assert bucket_from_volume(5000) == "high"
    assert bucket_from_volume(50_000) == "high"


def test_score_from_volume_is_log_scaled_in_unit_interval():
    assert score_from_volume(None) == pytest.approx(0.0, abs=1e-6)
    assert 0 < score_from_volume(50) < 1
    assert score_from_volume(100_000) == pytest.approx(1.0, rel=1e-3)


def test_decompose_prompt_for_handyman_example():
    variants = decompose_prompt("cheapest way to hire a handyman in Sydney")
    assert any("handyman" in v for v in variants)
    # Verb + tail is included so we can DataForSEO-query "hire handyman".
    assert any(v == "hire handyman" for v in variants)
    assert len(variants) <= 5


def test_decompose_prompt_for_smb_crm():
    variants = decompose_prompt("best crm for small business")
    assert any("crm" in v for v in variants)
    assert variants[0] != ""
    assert len(set(variants)) == len(variants)


def test_decompose_prompt_empty_returns_empty():
    assert decompose_prompt("") == []
    assert decompose_prompt("???") == []


# ---------------------------------------------------------------------------
# resolve_demand — 4-step fallback (with stubs)
# ---------------------------------------------------------------------------
class _FakePrompt:
    """Minimal Prompt stand-in for resolver tests (no SQLAlchemy involved)."""

    def __init__(self, text: str, locale: str = "en-AU") -> None:
        self.id = uuid4()
        self.text = text
        self.locale = locale
        self.created_at = datetime.now(timezone.utc)
        self.enabled = True
        self.demand_score = None
        self.demand_bucket = None
        self.demand_source = None
        self.demand_variant = None
        self.demand_raw_volume = None
        self.demand_refreshed_at = None


class _FakeSession:
    """No-op session used by the resolver's internal_demand_index path.

    The resolver only calls db.scalars().all() / db.scalar() for the
    internal step; we return empty results so that step yields 0 and the
    default fallback kicks in.
    """

    def scalars(self, _stmt: Any):  # noqa: D401
        class _Empty:
            def all(self_inner):  # noqa: D401
                return []

        return _Empty()

    def scalar(self, _stmt: Any):  # noqa: D401
        return 0


@pytest.fixture(autouse=True)
def _reset_cache_between_tests():
    cache.reset_for_tests()
    yield
    cache.reset_for_tests()


def _patch_dfs(monkeypatch, vol_map: dict[str, int], configured: bool = True):
    """Stub fetch_google_ads_search_volumes to return canned volumes."""
    import citationpulse.services.demand as demand_mod

    def _fake_fetch(keywords, *, location_code, language_code, settings=None):  # noqa: D401
        return [{"keyword": k, "search_volume": vol_map.get(normalise(k), 0)} for k in keywords]

    monkeypatch.setattr(demand_mod, "fetch_google_ads_search_volumes", _fake_fetch)
    monkeypatch.setattr(demand_mod, "dataforseo_configured", lambda: configured)


def test_resolve_demand_literal_step(monkeypatch):
    p = _FakePrompt("seo agency melbourne")
    _patch_dfs(monkeypatch, {normalise(p.text): 1200})
    r = resolve_demand(_FakeSession(), p)  # type: ignore[arg-type]
    assert r.source == "literal"
    assert r.raw_volume == 1200
    assert r.bucket == "medium"
    assert 0 < r.score < 1


def test_resolve_demand_falls_through_to_variant(monkeypatch):
    p = _FakePrompt("cheapest way to hire a handyman in Sydney")
    # Literal returns 0 (below threshold). Variant "hire handyman" wins.
    _patch_dfs(monkeypatch, {"hire handyman": 7400, "handyman sydney": 4500})
    r = resolve_demand(_FakeSession(), p)  # type: ignore[arg-type]
    assert r.source == "variant"
    assert r.raw_volume == 7400
    assert r.variant == "hire handyman"
    assert r.bucket == "high"


def test_resolve_demand_falls_through_to_default(monkeypatch):
    p = _FakePrompt("very obscure prompt nobody types")
    _patch_dfs(monkeypatch, {})  # all variants miss
    r = resolve_demand(_FakeSession(), p)  # type: ignore[arg-type]
    assert r.source == "default"
    assert r.score == DEFAULT_DEMAND_SCORE
    assert r.bucket == DEFAULT_DEMAND_BUCKET


def test_resolve_demand_default_when_dfs_not_configured(monkeypatch):
    p = _FakePrompt("any prompt at all")
    _patch_dfs(monkeypatch, {}, configured=False)
    r = resolve_demand(_FakeSession(), p)  # type: ignore[arg-type]
    assert r.source == "default"


def test_resolve_demand_result_is_never_null(monkeypatch):
    p = _FakePrompt("")
    _patch_dfs(monkeypatch, {}, configured=False)
    r = resolve_demand(_FakeSession(), p)  # type: ignore[arg-type]
    assert isinstance(r, DemandResult)
    assert r.score is not None
    assert r.bucket is not None
    assert r.score > 0


# ---------------------------------------------------------------------------
# Redis cache wrapper falls back to in-process
# ---------------------------------------------------------------------------
def test_cache_inproc_set_get_delete(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    cache.reset_for_tests()
    cache.set_json("foo:bar", {"v": 42}, ttl_s=60)
    assert cache.get_json("foo:bar") == {"v": 42}
    cache.delete("foo:bar")
    assert cache.get_json("foo:bar") is None


def test_cache_inproc_ttl_expires(monkeypatch):
    import time as _time

    monkeypatch.delenv("REDIS_URL", raising=False)
    cache.reset_for_tests()
    cache.set_json("ephemeral", {"v": 1}, ttl_s=1)
    assert cache.get_json("ephemeral") == {"v": 1}
    # Patch time.time inside the cache module so the TTL check sees the future.
    orig_time = cache.time.time
    cache.time.time = lambda: orig_time() + 5  # type: ignore[attr-defined]
    try:
        assert cache.get_json("ephemeral") is None
    finally:
        cache.time.time = orig_time  # type: ignore[attr-defined]
