"""Shared prompt×engine citation states for heatmap cells and gap classifiers."""

from __future__ import annotations

# Citations persist 0-based list indices; ranks 0–2 count as "top" (UI position 1–3).
BRAND_TOP_MAX_ZERO_BASED_POSITION = 2

MISSING = "MISSING"
COMPETITOR_ONLY = "COMPETITOR_ONLY"
CITED_TOP = "CITED_TOP"
CITED_LOWER = "CITED_LOWER"


def min_brand_position_zero_based(positions: list[int | None]) -> int | None:
    vals = [int(p) for p in positions if p is not None]
    return min(vals) if vals else None


def brand_tier_from_zero_based(position: int | None) -> str | None:
    """Return ``top`` or ``lower`` when the brand is cited; else ``None``."""
    if position is None:
        return "lower"
    return "top" if position <= BRAND_TOP_MAX_ZERO_BASED_POSITION else "lower"


def brand_tier_from_ui_position(position: int | None) -> str | None:
    """1-based position from ``cell_status_for_run`` (``1`` = first slot)."""
    if position is None:
        return "lower"
    zero = int(position) - 1
    return brand_tier_from_zero_based(zero)


def classifier_state_from_brand_and_comp(
    *,
    has_brand: bool,
    has_competitor: bool,
    min_brand_pos: int | None,
) -> str:
    if has_brand:
        tier = brand_tier_from_zero_based(min_brand_pos)
        return CITED_TOP if tier == "top" else CITED_LOWER
    if has_competitor:
        return COMPETITOR_ONLY
    return MISSING
