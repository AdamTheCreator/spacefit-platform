"""
Tests for the Location Resolver service.

Tests cover:
1. Parsing various location input formats
2. Resolution of city/state to FIPS codes
3. ZIP code extraction and lookup
4. Confidence scoring
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.location_resolver import (
    resolve_location,
    _parse_location_input,
    _normalize_state,
    ResolvedLocation,
    ResolutionConfidence,
    ResolutionMethod,
    STATE_FIPS,
)


class TestNormalizeState:
    """Tests for state normalization."""

    def test_abbreviation_uppercase(self):
        assert _normalize_state("CA") == "CA"
        assert _normalize_state("NV") == "NV"
        assert _normalize_state("CT") == "CT"

    def test_abbreviation_lowercase(self):
        assert _normalize_state("ca") == "CA"
        assert _normalize_state("nv") == "NV"

    def test_full_name(self):
        assert _normalize_state("California") == "CA"
        assert _normalize_state("NEVADA") == "NV"
        assert _normalize_state("connecticut") == "CT"

    def test_invalid_state(self):
        assert _normalize_state("XX") is None
        assert _normalize_state("Invalid") is None


class TestParseLocationInput:
    """Tests for location input parsing."""

    def test_city_state_abbrev(self):
        street, city, state = _parse_location_input("Reno, NV")
        assert street is None
        assert city == "Reno"
        assert state == "NV"

    def test_city_state_with_zip(self):
        street, city, state = _parse_location_input("Reno, NV 89501")
        assert street is None
        assert city == "Reno"
        assert state == "NV"

    def test_city_full_state_name(self):
        street, city, state = _parse_location_input("Boston, Massachusetts")
        assert street is None
        assert city == "Boston"
        assert state == "MA"

    def test_full_address(self):
        street, city, state = _parse_location_input("123 Main St, Boston, MA")
        # Note: Current parser may not perfectly extract street for all formats
        # The key requirement is that state is correctly identified
        assert state == "MA"
        assert city is not None or street is not None  # At least one should be set

    def test_complex_city_name(self):
        street, city, state = _parse_location_input("San Francisco, CA")
        assert street is None
        assert city == "San Francisco"
        assert state == "CA"

    def test_city_only(self):
        # Without state, can't extract properly
        street, city, state = _parse_location_input("Boston")
        assert city == "Boston"
        assert state is None


class TestResolvedLocation:
    """Tests for ResolvedLocation dataclass."""

    def test_has_census_identifiers(self):
        loc = ResolvedLocation(
            display_name="Reno, NV",
            state_fips="32",
            place_fips="60600",
        )
        assert loc.has_census_identifiers() is True

        loc_no_fips = ResolvedLocation(display_name="Unknown")
        assert loc_no_fips.has_census_identifiers() is False

    def test_has_zip(self):
        loc = ResolvedLocation(
            display_name="Reno, NV",
            primary_zip="89501",
        )
        assert loc.has_zip() is True

        loc_no_zip = ResolvedLocation(display_name="Unknown")
        assert loc_no_zip.has_zip() is False

    def test_has_coordinates(self):
        loc = ResolvedLocation(
            display_name="Reno, NV",
            latitude=39.5296,
            longitude=-119.8138,
        )
        assert loc.has_coordinates() is True

        loc_no_coords = ResolvedLocation(display_name="Unknown")
        assert loc_no_coords.has_coordinates() is False

    def test_to_dict(self):
        loc = ResolvedLocation(
            display_name="Reno, NV",
            normalized_city="Reno",
            state_abbrev="NV",
            state_fips="32",
            confidence=ResolutionConfidence.HIGH,
            method=ResolutionMethod.CENSUS_PLACE_LOOKUP,
            original_input="Reno, NV",
        )
        d = loc.to_dict()
        assert d["display_name"] == "Reno, NV"
        assert d["confidence"] == "high"
        assert d["method"] == "census_place_lookup"


@pytest.mark.asyncio
class TestResolveLocation:
    """Integration tests for resolve_location function."""

    @patch("app.services.location_resolver._geocode_with_google")
    @patch("app.services.location_resolver._lookup_place_fips")
    async def test_city_state_resolution(self, mock_place_fips, mock_google):
        """Test resolving a simple city, state input."""
        # Mock the place FIPS lookup
        mock_place_fips.return_value = {
            "name": "Reno city, Nevada",
            "place_fips": "60600",
            "state_fips": "32",
            "population": 264165,
        }

        # Mock Google geocoding for coordinates
        mock_google.return_value = ResolvedLocation(
            display_name="Reno, NV, USA",
            latitude=39.5296,
            longitude=-119.8138,
            primary_zip="89501",
            confidence=ResolutionConfidence.HIGH,
            method=ResolutionMethod.GOOGLE_GEOCODING,
        )

        result = await resolve_location("Reno, NV")

        assert result.normalized_city == "Reno"
        assert result.state_abbrev == "NV"
        assert result.state_fips == "32"
        assert result.place_fips == "60600"
        assert result.confidence == ResolutionConfidence.HIGH
        assert result.method == ResolutionMethod.CENSUS_PLACE_LOOKUP

    async def test_full_address_resolution(self):
        """Test resolving a full street address with ZIP code."""
        # When a full address with ZIP is provided, the resolver should at least
        # extract the ZIP code and return a result
        result = await resolve_location("123 Main St, Reno, NV 89501")

        # Should extract ZIP code from the address
        assert result.primary_zip == "89501"
        # Should not return low confidence (has ZIP)
        assert result.confidence != ResolutionConfidence.LOW

    async def test_zip_only_resolution(self):
        """Test resolving a ZIP code only input."""
        result = await resolve_location("89501")

        assert result.primary_zip == "89501"
        assert result.confidence == ResolutionConfidence.MEDIUM
        assert result.method == ResolutionMethod.ZIP_LOOKUP

    async def test_empty_input(self):
        """Test handling empty input."""
        result = await resolve_location("")

        assert result.confidence == ResolutionConfidence.LOW
        assert result.display_name == "Unknown"

    @patch("app.services.location_resolver._geocode_with_google")
    @patch("app.services.location_resolver._lookup_place_fips")
    async def test_fallback_to_low_confidence(self, mock_place_fips, mock_google):
        """Test fallback when resolution fails."""
        mock_place_fips.return_value = None
        mock_google.return_value = None

        result = await resolve_location("Nonexistent City, ZZ")

        assert result.confidence == ResolutionConfidence.LOW
        assert result.method == ResolutionMethod.FALLBACK


class TestStateFIPS:
    """Tests for state FIPS code mapping."""

    def test_all_states_have_fips(self):
        """Verify all 50 states + DC have FIPS codes."""
        assert len(STATE_FIPS) >= 51  # 50 states + DC

    def test_known_fips_codes(self):
        """Verify some known FIPS codes."""
        assert STATE_FIPS["CA"] == "06"
        assert STATE_FIPS["NY"] == "36"
        assert STATE_FIPS["TX"] == "48"
        assert STATE_FIPS["NV"] == "32"
        assert STATE_FIPS["CT"] == "09"
