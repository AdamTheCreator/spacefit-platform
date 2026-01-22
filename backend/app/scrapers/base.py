"""
Base scraper class defining the interface for all site scrapers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
from enum import Enum

from playwright.async_api import BrowserContext, Page


class DataType(str, Enum):
    """Types of data that can be scraped."""

    DEMOGRAPHICS = "demographics"
    VISITOR_TRAFFIC = "visitor_traffic"  # People visiting (Placer.ai mobile data)
    VEHICLE_TRAFFIC = "vehicle_traffic"  # Cars/VPD (SiteUSA road counts)
    TENANT_DATA = "tenant_data"
    PROPERTY_INFO = "property_info"
    TRADE_AREA = "trade_area"
    CUSTOMER_PROFILE = "customer_profile"  # Placer.ai audience overview
    VOID_ANALYSIS = "void_analysis"  # Missing tenant categories


@dataclass
class ScrapeResult:
    """Result from a scraping operation."""

    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    cached: bool = False
    source: str = ""


@dataclass
class ProgressUpdate:
    """Progress update for long-running scrapes."""

    step: str
    progress_pct: int  # 0-100
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


ProgressCallback = Callable[[ProgressUpdate], None]


class BaseScraper(ABC):
    """
    Abstract base class for all site scrapers.

    Subclasses must implement:
    - site_name: str property
    - site_url: str property
    - supported_data_types: list[DataType] property
    - login(): Perform login flow
    - scrape(): Extract data
    - is_logged_in(): Check login status
    """

    def __init__(
        self,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        self.progress_callback = progress_callback

    @property
    @abstractmethod
    def site_name(self) -> str:
        """Unique identifier for this site."""
        pass

    @property
    @abstractmethod
    def site_url(self) -> str:
        """Base URL for the site."""
        pass

    @property
    @abstractmethod
    def supported_data_types(self) -> list[DataType]:
        """List of data types this scraper can extract."""
        pass

    @property
    def display_name(self) -> str:
        """Human-readable name for display."""
        return self.site_name.replace("_", " ").title()

    @property
    def typical_login_seconds(self) -> int:
        """Typical time for login flow."""
        return 15

    @property
    def typical_scrape_seconds(self) -> int:
        """Typical time for a scrape operation."""
        return 30

    @abstractmethod
    async def login(
        self,
        context: BrowserContext,
        username: str,
        password: str,
    ) -> bool:
        """
        Perform login flow.

        Returns True if login successful, False otherwise.
        Should handle MFA prompts if applicable.
        """
        pass

    @abstractmethod
    async def is_logged_in(self, context: BrowserContext) -> bool:
        """Check if the current session is logged in."""
        pass

    @abstractmethod
    async def scrape(
        self,
        context: BrowserContext,
        data_type: DataType,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """
        Scrape data of the specified type.

        Args:
            context: Browser context to use
            data_type: Type of data to scrape
            params: Type-specific parameters (e.g., address, radius)

        Returns:
            ScrapeResult with data or error
        """
        pass

    def _report_progress(
        self,
        step: str,
        progress_pct: int,
        message: str,
    ) -> None:
        """Report progress to callback if set."""
        if self.progress_callback:
            self.progress_callback(
                ProgressUpdate(
                    step=step,
                    progress_pct=progress_pct,
                    message=message,
                )
            )

    async def _wait_for_navigation(
        self,
        page: Page,
        timeout_ms: int = 30000,
    ) -> None:
        """Wait for page navigation with configurable timeout."""
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)

    async def _safe_fill(
        self,
        page: Page,
        selector: str,
        value: str,
        timeout_ms: int = 10000,
    ) -> bool:
        """Safely fill a form field, returning False if not found."""
        try:
            await page.wait_for_selector(selector, timeout=timeout_ms)
            await page.fill(selector, value)
            return True
        except Exception:
            return False

    async def _safe_click(
        self,
        page: Page,
        selector: str,
        timeout_ms: int = 10000,
    ) -> bool:
        """Safely click an element, returning False if not found."""
        try:
            await page.wait_for_selector(selector, timeout=timeout_ms)
            await page.click(selector)
            return True
        except Exception:
            return False

    async def _get_text(
        self,
        page: Page,
        selector: str,
        default: str = "",
    ) -> str:
        """Safely get text content from an element."""
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                return text.strip()
        except Exception:
            pass
        return default

    async def _get_text_by_label(
        self,
        page: Page,
        label: str,
        default: str = "",
    ) -> str:
        """Get text value associated with a label using XPath."""
        selectors = [
            f'xpath=//*[contains(text(), "{label}")]/following-sibling::*[1]',
            f'xpath=//*[contains(text(), "{label}")]/../*[2]',
            f'xpath=//td[contains(text(), "{label}")]/following-sibling::td[1]',
        ]
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    return text.strip()
            except Exception:
                continue
        return default
