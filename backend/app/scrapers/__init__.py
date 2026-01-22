"""
Scraper registry for accessing site-specific scrapers.
"""

from typing import Type

from app.scrapers.base import BaseScraper, DataType, ScrapeResult, ProgressUpdate
from app.scrapers.siteusa import SiteUSAScraper
from app.scrapers.costar import CoStarScraper
from app.scrapers.placer import PlacerAIScraper


# Registry of available scrapers
SCRAPER_REGISTRY: dict[str, Type[BaseScraper]] = {
    "siteusa": SiteUSAScraper,
    "costar": CoStarScraper,
    "placer": PlacerAIScraper,
}


# Site configurations for UI
SITE_CONFIGS = {
    "siteusa": {
        "name": "SitesUSA",
        "description": "Demographics, foot traffic, and tenant data",
        "icon": "chart-bar",
        "url": "https://sitesusa.com",
        "data_types": ["demographics", "foot_traffic", "tenant_data", "trade_area"],
        "typical_duration_seconds": 45,
        "is_browser_based": True,
    },
    "costar": {
        "name": "CoStar",
        "description": "Premium tenant roster with lease details (rent, expiration, SF)",
        "icon": "building",
        "url": "https://www.costar.com",
        "data_types": ["property_info", "tenant_data"],
        "typical_duration_seconds": 60,
        "is_browser_based": True,
    },
    "placer": {
        "name": "Placer.ai",
        "description": "Foot traffic, customer profiles, void analysis (browser-based)",
        "icon": "users",
        "url": "https://analytics.placer.ai",
        "data_types": ["foot_traffic", "customer_profile", "void_analysis"],
        "typical_duration_seconds": 45,
        "is_browser_based": True,
    },
}


def get_scraper(
    site_name: str,
    progress_callback=None,
) -> BaseScraper:
    """Get a scraper instance by site name."""
    scraper_class = SCRAPER_REGISTRY.get(site_name.lower())
    if not scraper_class:
        available = ", ".join(SCRAPER_REGISTRY.keys())
        raise ValueError(
            f"No scraper available for site: {site_name}. "
            f"Available scrapers: {available}"
        )
    return scraper_class(progress_callback=progress_callback)


def list_available_scrapers() -> list[str]:
    """List all available scraper site names."""
    return list(SCRAPER_REGISTRY.keys())


def get_site_config(site_name: str) -> dict | None:
    """Get site configuration for UI display."""
    return SITE_CONFIGS.get(site_name.lower())


def list_all_sites() -> list[dict]:
    """List all site configurations including coming soon."""
    return [
        {"id": site_id, **config}
        for site_id, config in SITE_CONFIGS.items()
    ]


__all__ = [
    "BaseScraper",
    "DataType",
    "ScrapeResult",
    "ProgressUpdate",
    "SiteUSAScraper",
    "CoStarScraper",
    "PlacerAIScraper",
    "SCRAPER_REGISTRY",
    "SITE_CONFIGS",
    "get_scraper",
    "list_available_scrapers",
    "get_site_config",
    "list_all_sites",
]
