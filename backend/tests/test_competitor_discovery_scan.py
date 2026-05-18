"""Tests for scan-integrated competitor discovery helpers."""

from __future__ import annotations

from types import SimpleNamespace

from citationpulse.services.competitor_discovery_scan import (
    discovery_params_from_body,
    _locale_to_market,
)


def test_locale_to_market() -> None:
    assert _locale_to_market("en-AU") == "Australia"
    assert _locale_to_market("en-US") == "United States"


def test_discovery_params_from_body_defaults() -> None:
    body = SimpleNamespace(
        auto_discover_competitors=True,
        competitor_type=None,
        service=None,
        niche=None,
        location=None,
        excluded_competitors=[],
        locale="en-GB",
    )
    params = discovery_params_from_body(body)
    assert params["auto_discover"] is True
    assert params["market"] == "United Kingdom"
