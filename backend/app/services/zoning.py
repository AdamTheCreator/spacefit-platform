"""
Zoning Lookup Service

Provides GIS portal URLs for zoning lookups across target markets.
Covers key counties in Arizona, Nevada, and California.
"""

import logging

logger = logging.getLogger(__name__)

# GIS portal URLs mapped by state -> county -> portal URL
GIS_PORTALS: dict[str, dict[str, str]] = {
    "AZ": {
        "Maricopa": "https://gis.maricopa.gov/GIO/Zoning/",
        "Pima": "https://gis.pima.gov/maps/zoning/",
    },
    "NV": {
        "Clark": "https://gisgate.co.clark.nv.us/gismo/",
    },
    "CA": {
        "San Bernardino": "https://sbcounty.maps.arcgis.com/apps/webappviewer/",
        "Riverside": "https://gis.countyofriverside.us/Html5Viewer/",
        "Los Angeles": "https://planning.lacity.org/zoning/",
        "San Diego": "https://sdgis.sandag.org/",
    },
}


def get_zoning_portal_url(state: str, county: str) -> str | None:
    """
    Get the GIS portal URL for a specific state and county.

    Args:
        state: Two-letter state abbreviation (e.g., "AZ", "CA", "NV").
        county: County name (e.g., "Maricopa", "Los Angeles").

    Returns:
        The GIS portal URL string, or None if no portal is available
        for the given state/county combination.
    """
    state_upper = state.strip().upper()
    county_title = county.strip().title()

    state_portals = GIS_PORTALS.get(state_upper)
    if not state_portals:
        logger.debug("[zoning] No GIS portals available for state: %s", state_upper)
        return None

    url = state_portals.get(county_title)
    if not url:
        # Try case-insensitive match
        for portal_county, portal_url in state_portals.items():
            if portal_county.lower() == county.strip().lower():
                return portal_url
        logger.debug(
            "[zoning] No GIS portal available for %s County, %s",
            county_title,
            state_upper,
        )
        return None

    return url


def get_available_counties(state: str) -> list[str]:
    """
    Get the list of counties with available GIS portals for a state.

    Args:
        state: Two-letter state abbreviation (e.g., "AZ", "CA", "NV").

    Returns:
        List of county names with available zoning portals.
        Returns an empty list if the state has no portals.
    """
    state_upper = state.strip().upper()
    state_portals = GIS_PORTALS.get(state_upper)

    if not state_portals:
        return []

    return sorted(state_portals.keys())
