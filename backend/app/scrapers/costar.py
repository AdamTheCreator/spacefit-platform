"""
CoStar scraper implementation.

Scrapes tenant roster and property data from CoStar's web interface.
CoStar does not have a public API, so browser automation is required.

NOTE: Selectors are placeholders - need to be updated based on actual CoStar page structure.
The login flow and page structure should be verified with a real CoStar account.
"""

import asyncio
import logging
import time
from datetime import datetime, date
from typing import Any

from playwright.async_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout

from app.scrapers.base import BaseScraper, DataType, ScrapeResult

logger = logging.getLogger(__name__)

class CoStarScraper(BaseScraper):
    """
    Scraper for CoStar commercial real estate data.

    Supports:
    - Tenant roster with lease details (rent PSF, expiration, square footage)
    - Property information (building details, ownership, sale history)
    """

    @property
    def site_name(self) -> str:
        return "costar"

    @property
    def site_url(self) -> str:
        return "https://gateway.costar.com"

    @property
    def supported_data_types(self) -> list[DataType]:
        return [DataType.TENANT_DATA, DataType.PROPERTY_INFO]

    @property
    def typical_login_seconds(self) -> int:
        return 25  # CoStar can be slow to load

    @property
    def typical_scrape_seconds(self) -> int:
        return 60  # Property searches and data loading take time

    async def login(
        self,
        context: BrowserContext,
        username: str,
        password: str,
    ) -> bool:
        """
        Perform CoStar login.

        CoStar uses a multi-step login flow:
        1. Navigate to login page
        2. Enter email/username
        3. Click continue (may redirect to SSO)
        4. Enter password
        5. Handle any MFA if enabled
        """
        page = await context.new_page()
        start_time = time.time()

        try:
            self._report_progress("login", 5, "Navigating to CoStar...")

            # Navigate to login page
            await page.goto(self.site_url, timeout=30000)
            await self._wait_for_navigation(page, timeout_ms=15000)

            self._report_progress("login", 15, "Entering credentials...")

            # NOTE: These selectors are placeholders - update based on actual CoStar page
            # CoStar login page structure needs to be verified

            # Step 1: Enter username/email
            username_filled = await self._safe_fill(
                page,
                'input[type="email"], input[name="username"], input#email',
                username,
                timeout_ms=10000,
            )
            if not username_filled:
                logger.warning("[costar] Could not find username field")
                return False

            # Click continue/next button if present (CoStar may have multi-step login)
            await self._safe_click(page, 'button[type="submit"], button:has-text("Continue")')
            await asyncio.sleep(2)  # Wait for potential page transition

            self._report_progress("login", 30, "Entering password...")

            # Step 2: Enter password
            password_filled = await self._safe_fill(
                page,
                'input[type="password"], input[name="password"]',
                password,
                timeout_ms=10000,
            )
            if not password_filled:
                logger.warning("[costar] Could not find password field")
                return False

            self._report_progress("login", 45, "Submitting login...")

            # Submit login form
            await self._safe_click(page, 'button[type="submit"], button:has-text("Sign In"), button:has-text("Login")')

            # Wait for navigation after login
            await asyncio.sleep(3)
            await self._wait_for_navigation(page, timeout_ms=20000)

            self._report_progress("login", 70, "Verifying login...")

            # Check if login was successful
            # Look for indicators that we're logged in (dashboard, user menu, etc.)
            is_logged_in = await self._check_login_success(page)

            if is_logged_in:
                self._report_progress("login", 100, "Login successful")
                return True
            else:
                self._report_progress("login", 100, "Login failed - check credentials")
                return False

        except PlaywrightTimeout:
            logger.warning("[costar] Login timeout")
            self._report_progress("login", 100, "Login timeout")
            return False
        except Exception as e:
            logger.exception("[costar] Login error")
            self._report_progress("login", 100, f"Login error: {str(e)}")
            return False
        finally:
            await page.close()

    async def _check_login_success(self, page: Page) -> bool:
        """Check if login was successful by looking for logged-in indicators."""
        try:
            # Look for common logged-in indicators
            # These selectors need to be updated based on actual CoStar UI
            logged_in_indicators = [
                '[data-testid="user-menu"]',
                '.user-profile',
                '.account-menu',
                'button:has-text("Search")',
                '[class*="dashboard"]',
            ]

            for selector in logged_in_indicators:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        return True
                except Exception:
                    continue

            # Check URL - if redirected to dashboard/search, likely logged in
            current_url = page.url.lower()
            if any(x in current_url for x in ["search", "dashboard", "property", "market"]):
                return True

            # Check for login error messages
            error_indicators = [
                '.error-message',
                '[class*="error"]',
                'text=invalid',
                'text=incorrect',
            ]
            for selector in error_indicators:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        return False
                except Exception:
                    continue

            return False

        except Exception:
            logger.exception("[costar] Error checking login status")
            return False

    async def is_logged_in(self, context: BrowserContext) -> bool:
        """Check if the current session is logged in."""
        page = await context.new_page()
        try:
            # Navigate to a protected page
            await page.goto(f"{self.site_url}/property/search", timeout=30000)
            await asyncio.sleep(2)

            # Check if we're still logged in or redirected to login
            current_url = page.url.lower()

            # If we're on login page, not logged in
            if "login" in current_url or "signin" in current_url or "gateway" in current_url:
                return False

            # Check for logged-in indicators
            return await self._check_login_success(page)

        except Exception:
            logger.exception("[costar] Session check error")
            return False
        finally:
            await page.close()

    async def scrape(
        self,
        context: BrowserContext,
        data_type: DataType,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """
        Scrape data from CoStar.

        Args:
            context: Browser context to use
            data_type: TENANT_DATA or PROPERTY_INFO
            params: Should include 'address' for property lookup

        Returns:
            ScrapeResult with data or error
        """
        start_time = time.time()

        if data_type == DataType.TENANT_DATA:
            return await self._scrape_tenant_roster(context, params, start_time)
        elif data_type == DataType.PROPERTY_INFO:
            return await self._scrape_property_info(context, params, start_time)
        else:
            return ScrapeResult(
                success=False,
                error=f"Unsupported data type: {data_type}",
                duration_seconds=time.time() - start_time,
            )

    async def _scrape_tenant_roster(
        self,
        context: BrowserContext,
        params: dict[str, Any],
        start_time: float,
    ) -> ScrapeResult:
        """Scrape tenant roster for a property."""
        address = params.get("address", "")
        if not address:
            return ScrapeResult(
                success=False,
                error="Address is required",
                duration_seconds=time.time() - start_time,
            )

        page = await context.new_page()
        try:
            self._report_progress("scrape", 10, "Searching for property...")

            # Navigate to property search
            # NOTE: URL pattern needs to be verified with actual CoStar
            await page.goto(f"{self.site_url}/search?q={address}", timeout=30000)
            await self._wait_for_navigation(page, timeout_ms=15000)

            self._report_progress("scrape", 25, "Selecting property...")

            # Click on first search result
            # NOTE: Selector needs to be updated based on actual CoStar search results
            await self._safe_click(
                page,
                '.search-result:first-child, [data-testid="property-result"]:first-child',
                timeout_ms=10000,
            )
            await asyncio.sleep(2)
            await self._wait_for_navigation(page, timeout_ms=15000)

            self._report_progress("scrape", 40, "Navigating to tenant roster...")

            # Navigate to tenant/lease tab
            # NOTE: Selector needs to be updated
            await self._safe_click(
                page,
                'a:has-text("Tenants"), [data-tab="tenants"], .tenant-tab',
                timeout_ms=10000,
            )
            await asyncio.sleep(2)

            self._report_progress("scrape", 55, "Extracting tenant data...")

            # Extract tenant roster
            # NOTE: These selectors are placeholders
            tenants = await self._extract_tenants(page)

            self._report_progress("scrape", 90, "Processing data...")

            # Get property summary
            property_name = await self._get_text(page, '.property-name, h1')
            total_sqft = await self._get_text(page, '.total-sqft, [data-field="total_sqft"]')

            self._report_progress("scrape", 100, "Data extraction complete")

            return ScrapeResult(
                success=True,
                data={
                    "property_name": property_name,
                    "address": address,
                    "total_sqft": total_sqft,
                    "tenants": tenants,
                    "tenant_count": len(tenants),
                    "scraped_at": datetime.now().isoformat(),
                },
                duration_seconds=time.time() - start_time,
                source="CoStar",
            )

        except Exception as e:
            return ScrapeResult(
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time,
            )
        finally:
            await page.close()

    async def _extract_tenants(self, page: Page) -> list[dict]:
        """
        Extract tenant data from the tenant roster page.

        NOTE: Selectors are placeholders - need to be updated based on actual CoStar UI.
        """
        tenants = []

        try:
            # Find tenant rows - selector needs to be updated
            tenant_rows = await page.query_selector_all(
                '.tenant-row, tr[data-tenant], .lease-row'
            )

            for row in tenant_rows:
                try:
                    tenant = {
                        "name": await self._get_element_text(row, '.tenant-name, td:nth-child(1)'),
                        "suite": await self._get_element_text(row, '.suite, td:nth-child(2)'),
                        "square_feet": await self._get_element_text(row, '.sqft, td:nth-child(3)'),
                        "lease_type": await self._get_element_text(row, '.lease-type, td:nth-child(4)'),
                        "rent_psf": await self._get_element_text(row, '.rent, td:nth-child(5)'),
                        "lease_expiration": await self._get_element_text(row, '.expiration, td:nth-child(6)'),
                        "category": await self._get_element_text(row, '.category, td:nth-child(7)'),
                    }

                    # Only add if we got a name
                    if tenant["name"]:
                        tenants.append(tenant)

                except Exception:
                    logger.exception("[costar] Error extracting tenant row")
                    continue

        except Exception:
            logger.exception("[costar] Error finding tenant rows")

        return tenants

    async def _get_element_text(self, element, selector: str) -> str:
        """Get text from a child element within a parent element."""
        try:
            child = await element.query_selector(selector)
            if child:
                text = await child.inner_text()
                return text.strip()
        except Exception:
            pass
        return ""

    async def _scrape_property_info(
        self,
        context: BrowserContext,
        params: dict[str, Any],
        start_time: float,
    ) -> ScrapeResult:
        """Scrape property information."""
        address = params.get("address", "")
        if not address:
            return ScrapeResult(
                success=False,
                error="Address is required",
                duration_seconds=time.time() - start_time,
            )

        page = await context.new_page()
        try:
            self._report_progress("scrape", 10, "Searching for property...")

            await page.goto(f"{self.site_url}/search?q={address}", timeout=30000)
            await self._wait_for_navigation(page, timeout_ms=15000)

            self._report_progress("scrape", 25, "Selecting property...")

            # Click first result
            await self._safe_click(
                page,
                '.search-result:first-child',
                timeout_ms=10000,
            )
            await asyncio.sleep(2)
            await self._wait_for_navigation(page, timeout_ms=15000)

            self._report_progress("scrape", 50, "Extracting property details...")

            # Extract property info
            # NOTE: All selectors are placeholders
            property_data = {
                "name": await self._get_text(page, '.property-name, h1'),
                "address": address,
                "property_type": await self._get_text_by_label(page, "Property Type"),
                "year_built": await self._get_text_by_label(page, "Year Built"),
                "total_sqft": await self._get_text_by_label(page, "Total SF"),
                "lot_size": await self._get_text_by_label(page, "Lot Size"),
                "floors": await self._get_text_by_label(page, "Floors"),
                "parking_spaces": await self._get_text_by_label(page, "Parking"),
                "owner": await self._get_text_by_label(page, "Owner"),
                "last_sale_date": await self._get_text_by_label(page, "Last Sale Date"),
                "last_sale_price": await self._get_text_by_label(page, "Last Sale Price"),
                "occupancy": await self._get_text_by_label(page, "Occupancy"),
                "scraped_at": datetime.now().isoformat(),
            }

            self._report_progress("scrape", 100, "Property data extracted")

            return ScrapeResult(
                success=True,
                data=property_data,
                duration_seconds=time.time() - start_time,
                source="CoStar",
            )

        except Exception as e:
            return ScrapeResult(
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time,
            )
        finally:
            await page.close()


def format_tenant_roster(data: dict, address: str) -> str:
    """Format tenant roster data as markdown for chat display."""
    if not data.get("tenants"):
        return f"No tenant data found for {address}"

    tenants = data["tenants"]
    lines = [
        f"**Tenant Roster for {data.get('property_name', address)}**\n",
        f"*{address}*\n",
        f"**Total SF:** {data.get('total_sqft', 'N/A')}",
        f"**Tenant Count:** {len(tenants)}\n",
        "| Tenant | Suite | SF | Lease Type | Rent/SF | Expiration |",
        "|--------|-------|-----|------------|---------|------------|",
    ]

    for tenant in tenants[:25]:  # Limit to 25 for readability
        lines.append(
            f"| {tenant.get('name', 'N/A')} | "
            f"{tenant.get('suite', '')} | "
            f"{tenant.get('square_feet', '')} | "
            f"{tenant.get('lease_type', '')} | "
            f"{tenant.get('rent_psf', '')} | "
            f"{tenant.get('lease_expiration', '')} |"
        )

    if len(tenants) > 25:
        lines.append(f"\n*...and {len(tenants) - 25} more tenants*")

    lines.append("\n*Source: CoStar*")

    return "\n".join(lines)
