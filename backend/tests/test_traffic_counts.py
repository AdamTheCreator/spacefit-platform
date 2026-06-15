"""Unit tests for the traffic-counts (AADT) service.

The pure pieces — distance math, per-state field extraction, nearest-pick, and
formatting — are pinned here against the real provider configs (CA/NC/VA). The
live ArcGIS query needs network so it's exercised by mocking ``_query``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.traffic_counts import (
    TrafficCount,
    _extract_aadt,
    _extract_road,
    _geometry_distance_mi,
    _haversine_mi,
    covered_states,
    format_traffic_summary,
    get_traffic_count,
    pick_nearest,
    provider_for_state,
)

CA = provider_for_state("CA")
NC = provider_for_state("NC")
VA = provider_for_state("VA")


def _pt(aadt, lng, lat=34.0):
    """A point feature with a CA-style AADT attribute, for pick_nearest tests."""
    return {"attributes": {"AHEAD_AADT": aadt}, "geometry": {"x": lng, "y": lat}}


class TestProviders:
    def test_state_lookup_case_insensitive(self):
        assert provider_for_state("ca").name == "Caltrans"
        assert provider_for_state("NC").name == "NCDOT"
        assert provider_for_state("Va").name == "VDOT"

    def test_uncovered_and_empty(self):
        assert provider_for_state("TX") is None
        assert provider_for_state(None) is None
        assert provider_for_state("") is None

    def test_covered_states(self):
        assert set(covered_states()) >= {"CA", "NC", "VA"}


class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine_mi(34.0, -118.0, 34.0, -118.0) == pytest.approx(0, abs=1e-6)

    def test_one_degree_latitude_is_about_69_miles(self):
        assert _haversine_mi(34.0, -118.0, 35.0, -118.0) == pytest.approx(69, abs=1.0)


class TestGeometryDistance:
    def test_none_geometry(self):
        assert _geometry_distance_mi(None, 34.0, -118.0) is None
        assert _geometry_distance_mi({}, 34.0, -118.0) is None

    def test_point(self):
        d = _geometry_distance_mi({"x": -118.0, "y": 34.0}, 34.0, -118.0)
        assert d == pytest.approx(0, abs=0.01)

    def test_polyline_uses_nearest_vertex(self):
        geom = {"paths": [[[-118.01, 34.0], [-118.5, 34.0]]]}
        d = _geometry_distance_mi(geom, 34.0, -118.0)
        assert d == pytest.approx(_haversine_mi(34.0, -118.0, 34.0, -118.01), abs=0.01)

    def test_polygon_rings(self):
        geom = {"rings": [[[-118.02, 34.0], [-118.03, 34.0], [-118.02, 34.01]]]}
        d = _geometry_distance_mi(geom, 34.0, -118.0)
        assert d is not None and d > 0


class TestExtractAadt:
    def test_ca_takes_max_of_directional(self):
        assert _extract_aadt({"AHEAD_AADT": 100, "BACK_AADT": 250}, CA) == (250, None)

    def test_ca_ignores_zero_and_missing(self):
        assert _extract_aadt({"AHEAD_AADT": 0, "BACK_AADT": None}, CA) == (None, None)

    def test_nc_picks_latest_year_column(self):
        attrs = {"AADT_2018": 4000, "AADT_2022": 6900, "AADT_2021": None}
        assert _extract_aadt(attrs, NC) == (6900, 2022)

    def test_va_uses_adt_and_ignores_weekday_aawdt(self):
        # AAWDT (weekday-only) is a different metric and must not be used.
        assert _extract_aadt({"ADT": 2500, "AAWDT": 2600}, VA) == (2500, 2024)
        assert _extract_aadt({"ADT": None, "AAWDT": 2600}, VA) == (None, 2024)


class TestExtractRoad:
    def test_ca_prefixes_route_and_appends_description(self):
        road = _extract_road({"RTE": "10", "DESCRIPTION": "los angeles st"}, CA)
        assert road == "CA-10 (Los Angeles St)"

    def test_ca_does_not_double_prefix(self):
        assert _extract_road({"RTE": "CA-5"}, CA) == "CA-5"

    def test_nc_route(self):
        assert _extract_road({"ROUTE": "SR 3007"}, NC) == "SR 3007"

    def test_va_common_name(self):
        attrs = {"ROUTE_COMMON_NAME": "E Marshall ST"}
        assert _extract_road(attrs, VA) == "E Marshall ST"

    def test_fallback_when_no_fields(self):
        assert _extract_road({}, CA) == "a nearby road"


class TestPickNearest:
    def test_skips_features_without_aadt_and_picks_nearest(self):
        feats = [_pt(None, -118.0), _pt(50000, -118.03), _pt(30000, -118.004)]
        best = pick_nearest(feats, 34.0, -118.0, CA)
        assert best is not None
        assert best.aadt == 30000  # the closest one carrying a value
        assert 50000 in best.nearby

    def test_none_when_no_usable_features(self):
        assert pick_nearest([_pt(None, -118.0)], 34.0, -118.0, CA) is None


class TestFormat:
    def test_with_count(self):
        tc = TrafficCount(
            aadt=24500, road="CA-10", year=2023, distance_mi=0.2, source="Caltrans"
        )
        s = format_traffic_summary(tc)
        assert "24,500" in s and "CA-10" in s and "Caltrans" in s and "2023" in s

    def test_at_site(self):
        tc = TrafficCount(
            aadt=100, road="X", year=None, distance_mi=0.0, source="Caltrans"
        )
        assert "at the site" in format_traffic_summary(tc)

    def test_uncovered_state(self):
        msg = format_traffic_summary(None, "TX")
        assert "TX" in msg and "covered" in msg.lower()

    def test_covered_but_no_station(self):
        assert "near this address" in format_traffic_summary(None, "CA")


@pytest.mark.asyncio
class TestGetTrafficCount:
    @patch("app.services.traffic_counts._query")
    async def test_uncovered_state_skips_query(self, mock_query):
        result = await get_traffic_count(31.0, -97.0, "TX")
        assert result is None
        mock_query.assert_not_called()

    @patch("app.services.traffic_counts._query")
    async def test_returns_nearest_for_covered_state(self, mock_query):
        mock_query.return_value = [
            {"attributes": {"AHEAD_AADT": 25000}, "geometry": {"x": -118.0, "y": 34.0}},
        ]
        result = await get_traffic_count(34.0, -118.0, "CA")
        assert result is not None
        assert result.aadt == 25000
        assert result.state == "CA"
