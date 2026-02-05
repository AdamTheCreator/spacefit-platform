"""
SiteUSA scraper implementation.

Supports:
- Demographics data
- Vehicle traffic (VPD - Vehicles Per Day)
- Tenant roster data

Note: Selectors may need adjustment based on actual SiteUSA page structure.
"""

import time
import logging
from typing import Any

from playwright.async_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout

from app.scrapers.base import BaseScraper, DataType, ScrapeResult

logger = logging.getLogger(__name__)

class SiteUSAScraper(BaseScraper):
    """Scraper for SiteUSA commercial real estate data."""

    @property
    def site_name(self) -> str:
        return "siteusa"

    @property
    def site_url(self) -> str:
        return "https://regis.sitesusa.com"

    @property
    def supported_data_types(self) -> list[DataType]:
        return [
            DataType.DEMOGRAPHICS,
            DataType.VEHICLE_TRAFFIC,
            DataType.TENANT_DATA,
            DataType.TRADE_AREA,
        ]

    @property
    def typical_login_seconds(self) -> int:
        return 20

    @property
    def typical_scrape_seconds(self) -> int:
        return 45

    async def login(
        self,
        context: BrowserContext,
        username: str,
        password: str,
    ) -> bool:
        """Perform SiteUSA login."""
        page = await context.new_page()

        try:
            self._report_progress("login", 10, "Navigating to login page...")
            await page.goto(f"{self.site_url}/login", wait_until="networkidle")

            # SitesUSA REGIS uses Angular Material components
            email_selectors = [
                '#mat-input-0',  # REGIS username field
                'input[type="text"]',
                'input[name="email"]',
                'input[type="email"]',
                'input[name="username"]',
            ]

            password_selectors = [
                '#mat-input-1',  # REGIS password field
                'input[type="password"]',
                'input[name="password"]',
            ]

            submit_selectors = [
                'button[type="submit"]',  # REGIS uses this
                'button:has-text("Sign In")',
                'button:has-text("Log In")',
                'input[type="submit"]',
            ]

            self._report_progress("login", 30, "Entering credentials...")

            # Find and fill email/username
            email_filled = False
            for selector in email_selectors:
                if await self._safe_fill(page, selector, username, timeout_ms=3000):
                    email_filled = True
                    break

            if not email_filled:
                self._report_progress("login", 100, "Could not find email/username field")
                return False

            # Find and fill password
            password_filled = False
            for selector in password_selectors:
                if await self._safe_fill(page, selector, password, timeout_ms=3000):
                    password_filled = True
                    break

            if not password_filled:
                self._report_progress("login", 100, "Could not find password field")
                return False

            self._report_progress("login", 50, "Submitting login form...")

            # Click submit
            submit_clicked = False
            for selector in submit_selectors:
                if await self._safe_click(page, selector, timeout_ms=3000):
                    submit_clicked = True
                    break

            if not submit_clicked:
                # Try pressing Enter as fallback
                await page.keyboard.press("Enter")

            # Wait for redirect
            await page.wait_for_load_state("networkidle", timeout=20000)

            # Add extra wait for Angular to settle
            await page.wait_for_timeout(2000)

            logger.debug("[siteusa] After login navigation complete")

            self._report_progress("login", 80, "Checking login status...")

            # Check for successful login
            is_dashboard = await self._is_on_dashboard(page)
            logger.debug("[siteusa] Is on dashboard: %s", is_dashboard)

            if is_dashboard:
                self._report_progress("login", 100, "Login successful!")
                return True

            # Take screenshot for debugging
            try:
                await page.screenshot(path="/tmp/siteusa_login_debug.png")
                logger.debug("[siteusa] Screenshot saved to /tmp/siteusa_login_debug.png")
            except Exception:
                logger.exception("[siteusa] Could not save screenshot")

            # Check for error messages (including Angular Material errors)
            error_selectors = [
                ".mat-error",  # Angular Material error
                "mat-error",   # Angular Material error element
                ".error-message",
                ".alert-danger",
                ".alert-error",
                '[class*="error"]',
                '[role="alert"]',
            ]

            for selector in error_selectors:
                error_elements = await page.query_selector_all(selector)
                for error_el in error_elements:
                    try:
                        error_text = await error_el.inner_text()
                        if error_text.strip():
                            # Handle "already logged in" specially
                            if "already logged in" in error_text.lower():
                                self._report_progress("login", 100, f"Login failed: {error_text}. Please log out from other devices/sessions first.")
                            else:
                                self._report_progress("login", 100, f"Login failed: {error_text}")
                            return False
                    except Exception:
                        continue

            self._report_progress("login", 100, "Login failed - could not verify success")
            return False

        except PlaywrightTimeout:
            self._report_progress("login", 100, "Login timed out")
            return False
        except Exception as e:
            self._report_progress("login", 100, f"Login error: {str(e)}")
            return False
        finally:
            await page.close()

    async def _is_on_dashboard(self, page: Page) -> bool:
        """Check if we're on the dashboard (logged in)."""
        url = page.url.lower()

        # Check URL patterns - REGIS redirects to /map after login
        dashboard_patterns = ["/dashboard", "/home", "/account", "/my-", "/map", "/reports"]
        if any(pattern in url for pattern in dashboard_patterns):
            return True

        # If we're still on login page, we're not logged in
        if "/login" in url:
            return False

        # Check for logged-in indicators
        logged_in_selectors = [
            '[data-testid="user-menu"]',
            ".user-profile",
            ".user-avatar",
            'a[href*="logout"]',
            'button:has-text("Logout")',
            'button:has-text("Sign Out")',
            '[class*="dashboard"]',
            '[class*="account-menu"]',
            'app-header',  # REGIS app header
            'app-sidebar',  # REGIS sidebar
        ]

        for selector in logged_in_selectors:
            if await page.query_selector(selector):
                return True

        # Check for absence of login form (Sign In text)
        sign_in_header = await page.query_selector('[data-cy="sign-in-lbl"]')
        if sign_in_header:
            return False  # Still on login page

        return False

    async def is_logged_in(self, context: BrowserContext) -> bool:
        """Check if current session is logged in."""
        page = await context.new_page()

        try:
            # Navigate to a page that requires auth
            await page.goto(f"{self.site_url}/dashboard", wait_until="networkidle")

            # If we get redirected to login, we're not logged in
            if "/login" in page.url.lower():
                return False

            return await self._is_on_dashboard(page)
        except Exception:
            return False
        finally:
            await page.close()

    async def scrape(
        self,
        context: BrowserContext,
        data_type: DataType,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """Scrape data from SiteUSA."""
        start_time = time.time()

        try:
            if data_type == DataType.DEMOGRAPHICS:
                result = await self._scrape_demographics(context, params)
            elif data_type == DataType.VEHICLE_TRAFFIC:
                result = await self._scrape_vehicle_traffic(context, params)
            elif data_type == DataType.TENANT_DATA:
                result = await self._scrape_tenant_data(context, params)
            elif data_type == DataType.TRADE_AREA:
                result = await self._scrape_trade_area(context, params)
            else:
                return ScrapeResult(
                    success=False,
                    error=f"Unsupported data type: {data_type}",
                    duration_seconds=time.time() - start_time,
                    source=self.site_name,
                )

            result.duration_seconds = time.time() - start_time
            result.source = self.site_name
            return result

        except Exception as e:
            return ScrapeResult(
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time,
                source=self.site_name,
            )

    async def _scrape_demographics(
        self,
        context: BrowserContext,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """Scrape demographics data for an address."""
        address = params.get("address")
        radius_miles = params.get("radius_miles", 3)

        if not address:
            return ScrapeResult(success=False, error="Address is required")

        page = await context.new_page()

        try:
            self._report_progress("demographics", 10, "Navigating to demographics...")

            # Try to navigate to demographics section
            demo_urls = [
                f"{self.site_url}/demographics",
                f"{self.site_url}/reports/demographics",
                f"{self.site_url}/analysis/demographics",
            ]

            navigated = False
            for url in demo_urls:
                try:
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                    navigated = True
                    break
                except Exception:
                    continue

            if not navigated:
                # Try finding demographics link from dashboard
                await page.goto(f"{self.site_url}/dashboard", wait_until="networkidle")
                link_selectors = [
                    'a:has-text("Demographics")',
                    'a[href*="demographics"]',
                    'button:has-text("Demographics")',
                ]
                for selector in link_selectors:
                    if await self._safe_click(page, selector, timeout_ms=5000):
                        await self._wait_for_navigation(page)
                        navigated = True
                        break

            self._report_progress("demographics", 25, "Entering address...")

            # Find and fill address search
            address_selectors = [
                'input[name="address"]',
                'input[placeholder*="address"]',
                'input[placeholder*="Address"]',
                'input[type="search"]',
                "#address-search",
            ]

            address_filled = False
            for selector in address_selectors:
                if await self._safe_fill(page, selector, address, timeout_ms=5000):
                    address_filled = True
                    break

            if not address_filled:
                return ScrapeResult(
                    success=False,
                    error="Could not find address search field",
                )

            # Set radius if available
            radius_selectors = [
                'select[name="radius"]',
                'select[id*="radius"]',
                'input[name="radius"]',
            ]

            for selector in radius_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        tag = await element.evaluate("el => el.tagName")
                        if tag.lower() == "select":
                            await page.select_option(selector, str(radius_miles))
                        else:
                            await page.fill(selector, str(radius_miles))
                        break
                except Exception:
                    continue

            self._report_progress("demographics", 40, "Running search...")

            # Submit search
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Search")',
                'button:has-text("Run Report")',
                'button:has-text("Generate")',
            ]

            for selector in submit_selectors:
                if await self._safe_click(page, selector, timeout_ms=5000):
                    break
            else:
                await page.keyboard.press("Enter")

            # Wait for results
            self._report_progress("demographics", 60, "Waiting for results...")

            result_selectors = [
                ".demographics-results",
                ".report-results",
                '[class*="results"]',
                "table",
                ".data-table",
            ]

            results_found = False
            for selector in result_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=30000)
                    results_found = True
                    break
                except Exception:
                    continue

            if not results_found:
                # Check if page has any data
                await page.wait_for_timeout(5000)

            self._report_progress("demographics", 80, "Extracting data...")

            # Extract demographics data
            data = await self._extract_demographics_data(page)

            if not data or all(v is None for v in data.values() if v != "SiteUSA"):
                return ScrapeResult(
                    success=False,
                    error="Could not extract demographics data from page",
                )

            self._report_progress("demographics", 100, "Complete!")

            return ScrapeResult(success=True, data=data)

        except PlaywrightTimeout:
            return ScrapeResult(success=False, error="Request timed out")
        except Exception as e:
            return ScrapeResult(success=False, error=str(e))
        finally:
            await page.close()

    async def _extract_demographics_data(self, page: Page) -> dict[str, Any]:
        """Extract demographics data from results page."""
        data = {}

        # Try to extract common demographic fields
        field_mappings = {
            "population": ["Population", "Total Population", "Pop."],
            "households": ["Households", "Total Households", "HH"],
            "median_income": [
                "Median Income",
                "Median HH Income",
                "Median Household Income",
            ],
            "avg_income": ["Average Income", "Avg. HH Income", "Average Household Income"],
            "avg_age": ["Average Age", "Median Age", "Avg. Age"],
            "daytime_pop": ["Daytime Population", "Daytime Pop.", "Day Pop."],
        }

        for field_key, labels in field_mappings.items():
            for label in labels:
                value = await self._get_text_by_label(page, label)
                if value:
                    # Try to parse numeric value
                    cleaned = value.replace(",", "").replace("$", "").strip()
                    try:
                        if "." in cleaned:
                            data[field_key] = float(cleaned)
                        else:
                            data[field_key] = int(cleaned)
                    except ValueError:
                        data[field_key] = value
                    break

        # Try to get data from tables
        tables = await page.query_selector_all("table")
        for table in tables:
            rows = await table.query_selector_all("tr")
            for row in rows:
                cells = await row.query_selector_all("td, th")
                if len(cells) >= 2:
                    label_el = cells[0]
                    value_el = cells[1]
                    label = (await label_el.inner_text()).strip().lower()
                    value = (await value_el.inner_text()).strip()

                    if "population" in label and "population" not in data:
                        data["population"] = value
                    elif "household" in label and "households" not in data:
                        data["households"] = value
                    elif "income" in label and "median_income" not in data:
                        data["median_income"] = value

        data["source"] = "SiteUSA"
        return data

    async def _scrape_vehicle_traffic(
        self,
        context: BrowserContext,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """Scrape vehicle traffic (VPD) data."""
        address = params.get("address")

        if not address:
            return ScrapeResult(success=False, error="Address is required")

        page = await context.new_page()

        try:
            self._report_progress("vehicle_traffic", 10, "Navigating to traffic analysis...")

            # Navigate to vehicle traffic / VPD section
            traffic_urls = [
                f"{self.site_url}/traffic",
                f"{self.site_url}/vehicle-traffic",
                f"{self.site_url}/vpd",
                f"{self.site_url}/analysis/traffic",
            ]

            for url in traffic_urls:
                try:
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                    break
                except Exception:
                    continue

            self._report_progress("vehicle_traffic", 30, "Searching location...")

            # Search for address
            await self._safe_fill(page, 'input[type="search"], input[name="address"]', address)
            await page.keyboard.press("Enter")
            await self._wait_for_navigation(page)

            self._report_progress("vehicle_traffic", 60, "Extracting VPD data...")

            # Extract vehicle traffic data (VPD = Vehicles Per Day)
            data = {
                "primary_road_vpd": await self._get_text_by_label(page, "Primary Road VPD"),
                "secondary_road_vpd": await self._get_text_by_label(page, "Secondary Road VPD"),
                "intersection_vpd": await self._get_text_by_label(page, "Intersection VPD"),
                "peak_hours": await self._get_text_by_label(page, "Peak Hours"),
                "weekend_increase": await self._get_text_by_label(page, "Weekend Increase"),
                "source": "SiteUSA",
            }

            # Also try alternative labels
            if not data["primary_road_vpd"]:
                data["primary_road_vpd"] = await self._get_text_by_label(page, "VPD")
            if not data["primary_road_vpd"]:
                data["primary_road_vpd"] = await self._get_text_by_label(page, "Vehicles Per Day")
            if not data["primary_road_vpd"]:
                data["primary_road_vpd"] = await self._get_text_by_label(page, "Daily Traffic")

            self._report_progress("vehicle_traffic", 100, "Complete!")

            return ScrapeResult(success=True, data=data)

        except Exception as e:
            return ScrapeResult(success=False, error=str(e))
        finally:
            await page.close()

    async def _scrape_tenant_data(
        self,
        context: BrowserContext,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """Scrape tenant roster data."""
        address = params.get("address")

        if not address:
            return ScrapeResult(success=False, error="Address is required")

        page = await context.new_page()

        try:
            self._report_progress("tenant_data", 10, "Navigating to tenant search...")

            await page.goto(f"{self.site_url}/tenants", wait_until="networkidle")

            self._report_progress("tenant_data", 30, "Searching location...")

            await self._safe_fill(page, 'input[type="search"], input[name="address"]', address)
            await page.keyboard.press("Enter")
            await self._wait_for_navigation(page)

            self._report_progress("tenant_data", 60, "Extracting tenant list...")

            # Extract tenant list
            tenants = []
            tenant_elements = await page.query_selector_all(".tenant-item, .business-item, tr.tenant")

            for el in tenant_elements[:50]:  # Limit to 50 tenants
                name = await self._get_text(el, ".tenant-name, .business-name, td:first-child")
                category = await self._get_text(el, ".category, td:nth-child(2)")
                if name:
                    tenants.append({"name": name, "category": category})

            data = {
                "tenants": tenants,
                "total_count": len(tenants),
                "source": "SiteUSA",
            }

            self._report_progress("tenant_data", 100, "Complete!")

            return ScrapeResult(success=True, data=data)

        except Exception as e:
            return ScrapeResult(success=False, error=str(e))
        finally:
            await page.close()

    async def _scrape_trade_area(
        self,
        context: BrowserContext,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """Scrape trade area analysis data."""
        address = params.get("address")
        radius_miles = params.get("radius_miles", 3)

        if not address:
            return ScrapeResult(success=False, error="Address is required")

        # Trade area often combines demographics and traffic
        demo_result = await self._scrape_demographics(context, params)
        traffic_result = await self._scrape_vehicle_traffic(context, params)

        combined_data = {
            "address": address,
            "radius_miles": radius_miles,
            "demographics": demo_result.data if demo_result.success else None,
            "vehicle_traffic": traffic_result.data if traffic_result.success else None,
            "source": "SiteUSA",
        }

        if not demo_result.success and not traffic_result.success:
            return ScrapeResult(
                success=False,
                error="Could not retrieve trade area data",
            )

        return ScrapeResult(success=True, data=combined_data)
