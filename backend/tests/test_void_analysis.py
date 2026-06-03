"""Unit tests for void-analysis helpers.

`affordability_tier` is pure + deterministic, so we can pin the demographic
"scrubbing" boundaries here without touching an LLM.
"""

import pytest

from app.services.void_analysis import affordability_tier


@pytest.mark.parametrize(
    "income, expected",
    [
        (None, "unknown"),
        (0, "unknown"),
        (-5, "unknown"),
        (35_000, "value"),
        (49_999, "value"),
        (50_000, "moderate"),
        (89_999, "moderate"),
        (90_000, "affluent"),
        (149_999, "affluent"),
        (150_000, "luxury"),
        (250_000, "luxury"),
    ],
)
def test_affordability_tier_boundaries(income, expected):
    assert affordability_tier(income)["key"] == expected


def test_affordability_tier_always_has_label():
    # The label is interpolated into the scrub prompt, so it must be a
    # non-empty string for every tier.
    for income in (None, 30_000, 60_000, 120_000, 200_000):
        tier = affordability_tier(income)
        assert isinstance(tier["label"], str)
        assert tier["label"]
