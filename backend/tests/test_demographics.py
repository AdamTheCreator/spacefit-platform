"""
Tests for demographics analysis with Location Resolver integration.

Tests verify:
1. "Reno, NV" produces demographics without asking for ZIP
2. City-only inputs are properly resolved
3. Place-level demographics work
4. Fallback to county/ZCTA when needed
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys

from app.services.census import (
    analyze_demographics,
    get_place_demographics,
    _format_demographic_data_section,
    DemographicData,
)
from app.services.location_resolver import (
    ResolvedLocation,
    ResolutionConfidence,
    ResolutionMethod,
)


@pytest.fixture
def sample_demographic_data():
    """Sample demographic data for testing."""
    return DemographicData(
        geography_name="Reno city, Nevada",
        total_population=264165,
        median_household_income=65123,
        median_age=36.5,
        population_under_18=52833,
        population_18_34=66041,
        population_35_54=79250,
        population_55_plus=66041,
        bachelors_degree_or_higher_pct=32.5,
        labor_force=145000,
        employed=140000,
        unemployment_rate=3.4,
        total_housing_units=115000,
        owner_occupied_pct=48.5,
        renter_occupied_pct=51.5,
        median_home_value=425000,
        total_households=108000,
        avg_household_size=2.45,
        family_households_pct=58.2,
    )


@pytest.fixture
def mock_resolved_reno():
    """Mock resolved location for Reno, NV."""
    return ResolvedLocation(
        display_name="Reno city, Nevada",
        normalized_city="Reno",
        state_abbrev="NV",
        state_fips="32",
        place_fips="60600",
        latitude=39.5296,
        longitude=-119.8138,
        primary_zip="89501",
        confidence=ResolutionConfidence.HIGH,
        method=ResolutionMethod.CENSUS_PLACE_LOOKUP,
        original_input="Reno, NV",
    )


class TestFormatDemographicDataSection:
    """Tests for formatting demographic data."""

    def test_format_includes_all_sections(self, sample_demographic_data):
        """Verify all demographic sections are formatted."""
        result = _format_demographic_data_section(sample_demographic_data)

        assert "Population & Age" in result
        assert "Income & Economics" in result
        assert "Education" in result
        assert "Housing" in result
        assert "Households" in result

    def test_format_includes_key_metrics(self, sample_demographic_data):
        """Verify key metrics are included."""
        result = _format_demographic_data_section(sample_demographic_data)

        assert "264,165" in result  # Population
        assert "$65,123" in result  # Income
        assert "36.5" in result  # Median age
        assert "3.4%" in result  # Unemployment


@pytest.mark.asyncio
class TestAnalyzeDemographics:
    """Integration tests for analyze_demographics function."""

    async def test_reno_nv_produces_demographics(
        self,
        sample_demographic_data,
        mock_resolved_reno,
    ):
        """
        Test that 'Reno, NV' produces demographics without asking for ZIP.
        This is the core Issue 2 acceptance criteria.
        """
        # Mock the analytics module
        mock_analytics_instance = MagicMock()
        mock_analytics_instance.record_location_resolution = MagicMock()

        # Create async mock for resolve_location
        async def mock_resolve(location):
            return mock_resolved_reno

        # Create async mock for geocode_address
        async def mock_geocode(location):
            return None  # No street address match

        # Create async mock for get_place_demographics
        async def mock_get_place(state_fips, place_fips):
            return sample_demographic_data

        with patch("app.services.location_resolver.resolve_location", side_effect=mock_resolve), \
             patch("app.services.census.geocode_address", side_effect=mock_geocode), \
             patch("app.services.census.get_place_demographics", side_effect=mock_get_place), \
             patch("app.services.analytics.get_analytics", return_value=mock_analytics_instance):

            result = await analyze_demographics("Reno, NV")

            # Verify we got demographics, not an error
            assert "Unable to find demographics" not in result
            assert "Tips for better results" not in result

            # Verify key data is present
            assert "Reno" in result
            assert "264,165" in result  # Population
            assert "Source: U.S. Census Bureau" in result

    async def test_city_state_without_zip(self, sample_demographic_data):
        """Test various city/state inputs without ZIP codes."""
        mock_analytics_instance = MagicMock()
        mock_analytics_instance.record_location_resolution = MagicMock()

        test_cases = [
            ("Boston, MA", "MA", "25"),
            ("San Francisco, CA", "CA", "06"),
            ("Austin, TX", "TX", "48"),
        ]

        for location, state_abbrev, state_fips in test_cases:
            city = location.split(",")[0].strip()

            mock_resolved = ResolvedLocation(
                display_name=f"{city} city, {state_abbrev}",
                normalized_city=city,
                state_abbrev=state_abbrev,
                state_fips=state_fips,
                place_fips="12345",
                confidence=ResolutionConfidence.HIGH,
                method=ResolutionMethod.CENSUS_PLACE_LOOKUP,
                original_input=location,
            )

            async def mock_resolve(loc):
                return mock_resolved

            async def mock_geocode(loc):
                return None

            async def mock_get_place(sf, pf):
                return sample_demographic_data

            with patch("app.services.location_resolver.resolve_location", side_effect=mock_resolve), \
                 patch("app.services.census.geocode_address", side_effect=mock_geocode), \
                 patch("app.services.census.get_place_demographics", side_effect=mock_get_place), \
                 patch("app.services.analytics.get_analytics", return_value=mock_analytics_instance):

                result = await analyze_demographics(location)

                # Should not ask for ZIP
                assert "Tips for better results" not in result, f"Failed for {location}"
                assert "Unable to find" not in result, f"Failed for {location}"

    async def test_fallback_to_zip_when_place_fails(self, sample_demographic_data):
        """Test fallback to ZCTA when place lookup fails."""
        mock_analytics_instance = MagicMock()
        mock_analytics_instance.record_location_resolution = MagicMock()

        mock_resolved = ResolvedLocation(
            display_name="Small Town, NV",
            normalized_city="Small Town",
            state_abbrev="NV",
            state_fips="32",
            place_fips=None,  # No place FIPS
            primary_zip="89001",
            confidence=ResolutionConfidence.MEDIUM,
            method=ResolutionMethod.GOOGLE_GEOCODING,
            original_input="Small Town, NV",
        )

        async def mock_resolve(loc):
            return mock_resolved

        async def mock_geocode(loc):
            return None

        async def mock_zcta(zip_code):
            return sample_demographic_data

        with patch("app.services.location_resolver.resolve_location", side_effect=mock_resolve), \
             patch("app.services.census.geocode_address", side_effect=mock_geocode), \
             patch("app.services.census.get_zcta_demographics", side_effect=mock_zcta) as mock_zcta_patch, \
             patch("app.services.analytics.get_analytics", return_value=mock_analytics_instance):

            result = await analyze_demographics("Small Town, NV")

            # Should not show error
            assert "Unable to find" not in result


@pytest.mark.asyncio
class TestGetPlaceDemographics:
    """Tests for place-level demographics lookup."""

    @patch("httpx.AsyncClient")
    async def test_successful_place_lookup(self, mock_client):
        """Test successful Census API call for place demographics."""
        # Mock the Census API response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            ["NAME", "B01003_001E", "B19013_001E", "state", "place"],
            ["Reno city, Nevada", "264165", "65123", "32", "60600"],
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client.return_value = mock_client_instance

        result = await get_place_demographics("32", "60600")

        assert result is not None
        assert result.total_population == 264165
        assert result.geography_name == "Reno city, Nevada"

    @patch("httpx.AsyncClient")
    async def test_place_not_found(self, mock_client):
        """Test handling when place is not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            ["NAME", "B01003_001E", "state", "place"],
        ]  # No data rows
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client.return_value = mock_client_instance

        result = await get_place_demographics("32", "99999")

        assert result is None


class TestAcceptanceCriteria:
    """
    Tests verifying the acceptance criteria from the requirements.

    Issue 2 Acceptance Criteria:
    - "Reno, NV" produces demographics without asking for ZIP
    """

    @pytest.mark.asyncio
    async def test_acceptance_reno_nv_no_zip_required(
        self,
        sample_demographic_data,
        mock_resolved_reno,
    ):
        """
        ACCEPTANCE TEST: Reno, NV produces demographics without asking for ZIP.

        This directly tests the Issue 2 acceptance criteria.
        """
        mock_analytics_instance = MagicMock()
        mock_analytics_instance.record_location_resolution = MagicMock()

        async def mock_resolve(loc):
            return mock_resolved_reno

        async def mock_geocode(loc):
            return None

        async def mock_get_place(sf, pf):
            return sample_demographic_data

        with patch("app.services.location_resolver.resolve_location", side_effect=mock_resolve), \
             patch("app.services.census.geocode_address", side_effect=mock_geocode), \
             patch("app.services.census.get_place_demographics", side_effect=mock_get_place), \
             patch("app.services.analytics.get_analytics", return_value=mock_analytics_instance):

            result = await analyze_demographics("Reno, NV")

            # MUST NOT contain error messages asking for ZIP
            error_indicators = [
                "Unable to find demographics",
                "Tips for better results",
                "Include a ZIP code",
                "ZIP code to look up demographics",
            ]

            for indicator in error_indicators:
                assert indicator not in result, f"Found error indicator: {indicator}"

            # MUST contain actual demographics data
            assert "Population" in result
            assert "Income" in result
            assert "Census Bureau" in result
