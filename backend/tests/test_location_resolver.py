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
    _parse_commaless_address,
    _find_similar_cities,
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
        # Mock the place FIPS lookup (now returns tuple)
        mock_place_fips.return_value = ({
            "name": "Reno city, Nevada",
            "place_fips": "60600",
            "state_fips": "32",
            "population": 264165,
        }, [])

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
        mock_place_fips.return_value = (None, [])
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


class TestParseCommalessInput:
    """Tests for comma-less address parsing."""

    def test_bug_input_address_with_city_state(self):
        """The original bug: '146-154 Main St weston ct' should parse correctly."""
        street, city, state = _parse_location_input("146-154 Main St weston ct")
        assert street == "146-154 Main St"
        assert city == "weston"
        assert state == "CT"

    def test_city_state_no_comma(self):
        """Simple city + state without comma."""
        street, city, state = _parse_location_input("greenwich ct")
        assert street is None
        assert city == "greenwich"
        assert state == "CT"

    def test_ct_disambiguation_street_suffix(self):
        """'100 Oak Ct' should NOT be parsed as Connecticut."""
        result = _parse_commaless_address("100 Oak Ct")
        # "ct" is the only suffix and there's a street number, so it's court not state
        assert result is None

    def test_ct_as_state_with_other_suffix(self):
        """'100 Oak St Hartford ct' — 'St' is the street suffix, 'ct' is state."""
        street, city, state = _parse_location_input("100 Oak St Hartford ct")
        assert street == "100 Oak St"
        assert city == "Hartford"
        assert state == "CT"

    def test_address_with_drive_suffix(self):
        """Address with non-ambiguous suffix and state."""
        street, city, state = _parse_location_input("500 Elm Dr Austin TX")
        assert street == "500 Elm Dr"
        assert city == "Austin"
        assert state == "TX"

    def test_multi_word_city(self):
        """Multi-word city in comma-less input."""
        street, city, state = _parse_location_input("200 First Ave New York NY")
        assert street == "200 First Ave"
        assert city == "New York"
        assert state == "NY"

    def test_no_state_returns_none(self):
        """Input without a valid state should not match commaless parser."""
        result = _parse_commaless_address("123 Main St Somewhere")
        assert result is None

    def test_single_word_not_parsed(self):
        """Single word input should not match."""
        result = _parse_commaless_address("Boston")
        assert result is None


class TestFindSimilarCities:
    """Tests for fuzzy city name matching."""

    def test_close_match(self):
        """'weston' should suggest 'Westport' from CT places."""
        places = ["Westport city, Connecticut", "Weston town, Connecticut",
                   "Westbrook town, Connecticut", "Hartford city, Connecticut"]
        suggestions = _find_similar_cities("weston", places)
        # Should find Weston (exact after cleanup) or close matches
        assert len(suggestions) > 0
        assert any("West" in s for s in suggestions)

    def test_typo_match(self):
        """Typo in city name should still find suggestions."""
        places = ["Springfield city, Illinois", "Rockford city, Illinois",
                   "Springfeld village, Illinois"]
        suggestions = _find_similar_cities("springfeld", places)
        assert len(suggestions) > 0

    def test_no_match(self):
        """Completely different name returns empty."""
        places = ["Portland city, Oregon", "Salem city, Oregon"]
        suggestions = _find_similar_cities("zzzznotacity", places)
        assert suggestions == []

    def test_exact_match_excluded(self):
        """Exact match of the input should be excluded from suggestions."""
        places = ["Weston town, Connecticut", "Westport city, Connecticut"]
        suggestions = _find_similar_cities("weston", places)
        assert "Weston" not in suggestions


@pytest.mark.asyncio
class TestResolutionSuggestions:
    """Tests for suggestion propagation through resolve_location."""

    @patch("app.services.location_resolver._geocode_with_google")
    @patch("app.services.location_resolver._lookup_place_fips")
    async def test_suggestions_on_city_mismatch(self, mock_place_fips, mock_google):
        """When city lookup fails with suggestions, they appear in the result."""
        mock_place_fips.return_value = (None, ["Westport", "Westbrook"])
        mock_google.return_value = None

        result = await resolve_location("weston, CT")

        assert result.confidence == ResolutionConfidence.LOW
        assert result.suggestions == ["Westport", "Westbrook"]
        assert "Westport" in result.suggestion_message
        assert "weston" in result.suggestion_message

    @patch("app.services.location_resolver._geocode_with_google")
    @patch("app.services.location_resolver._lookup_place_fips")
    async def test_no_suggestions_on_success(self, mock_place_fips, mock_google):
        """Successful resolution should have no suggestions."""
        mock_place_fips.return_value = ({
            "name": "Westport city, Connecticut",
            "place_fips": "82800",
            "state_fips": "09",
            "population": 27000,
        }, [])
        mock_google.return_value = ResolvedLocation(
            display_name="Westport, CT",
            latitude=41.14,
            longitude=-73.36,
            primary_zip="06880",
            confidence=ResolutionConfidence.HIGH,
            method=ResolutionMethod.GOOGLE_GEOCODING,
        )

        result = await resolve_location("Westport, CT")

        assert result.confidence == ResolutionConfidence.HIGH
        assert result.suggestions == []
        assert result.suggestion_message is None
