"""
Placer.ai browser scraper implementation.

Supports:
- Visitor traffic data (visitor counts, peak times, dwell time)
- Customer profile / audience overview (actual visitor demographics)
- Void analysis (missing tenant categories)

This scraper uses browser automation to extract data from Placer.ai's web interface,
replacing the API-based approach which is cost-prohibitive.

Note: Placer.ai uses reCAPTCHA on their login page which cannot be bypassed
automatically. Users must perform manual login to establish a session, which
is then reused for subsequent automated operations.

Note: Selectors may need adjustment based on actual Placer.ai page structure.
"""

import time
import logging
from typing import Any

from playwright.async_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout

from app.scrapers.base import BaseScraper, DataType, LoginResult, ScrapeResult

logger = logging.getLogger(__name__)

class PlacerAIScraper(BaseScraper):
    """Scraper for Placer.ai foot traffic and customer analytics.

    IMPORTANT: Placer.ai uses reCAPTCHA which requires manual login.
    The typical workflow is:
    1. User performs manual login via debug script or UI
    2. Session cookies are saved
    3. Scraper reuses saved session for ~24 hours
    4. When session expires, manual re-login is required
    """

    @property
    def site_name(self) -> str:
        return "placer"

    @property
    def site_url(self) -> str:
        return "https://analytics.placer.ai"

    @property
    def supported_data_types(self) -> list[DataType]:
        return [
            DataType.VISITOR_TRAFFIC,
            DataType.CUSTOMER_PROFILE,
            DataType.VOID_ANALYSIS,
        ]

    @property
    def typical_login_seconds(self) -> int:
        return 15

    @property
    def typical_scrape_seconds(self) -> int:
        return 40

    @property
    def requires_manual_login(self) -> bool:
        """Placer.ai always requires manual login due to reCAPTCHA."""
        return True

    async def login(
        self,
        context: BrowserContext,
        username: str,
        password: str,
    ) -> bool:
        """Perform Placer.ai login.

        Note: This method may fail due to reCAPTCHA. For better error handling,
        use login_with_captcha_detection() instead.
        """
        page = await context.new_page()

        try:
            self._report_progress("login", 10, "Navigating to Placer.ai...")
            await page.goto(f"{self.site_url}/auth/signin", wait_until="networkidle")
            await page.wait_for_timeout(2000)  # Wait for JS to render

            # Check for CAPTCHA before attempting login
            captcha_detected, captcha_type = await self._detect_captcha(page)
            if captcha_detected:
                logger.warning("[placer] CAPTCHA detected (%s) - cannot proceed with automated login", captcha_type)
                self._report_progress(
                    "login", 100,
                    f"CAPTCHA ({captcha_type}) detected. Please use manual session refresh."
                )
                await self._save_debug_screenshot(page, "placer_captcha_on_load.png")
                return False

            # Placer.ai login form selectors (based on actual page inspection)
            email_selectors = [
                '[data-testid="email-input-field"]',
                'input[name="username"]',
                'input[placeholder*="company.com"]',
                'input[type="text"]',
            ]

            password_selectors = [
                '[data-testid="login-password-input"]',
                'input[name="password"]',
                'input[type="password"]',
            ]

            submit_selectors = [
                '[data-testid="login-page-login-button"]',
                'button[type="submit"]',
                'button:has-text("Login")',
            ]

            self._report_progress("login", 30, "Entering credentials...")

            # Fill email
            email_filled = False
            for selector in email_selectors:
                if await self._safe_fill(page, selector, username, timeout_ms=3000):
                    email_filled = True
                    break

            if not email_filled:
                self._report_progress("login", 100, "Could not find email field")
                return False

            # Fill password
            password_filled = False
            for selector in password_selectors:
                if await self._safe_fill(page, selector, password, timeout_ms=3000):
                    password_filled = True
                    break

            if not password_filled:
                self._report_progress("login", 100, "Could not find password field")
                return False

            # Check for CAPTCHA after filling credentials (sometimes appears here)
            captcha_detected, captcha_type = await self._detect_captcha(page)
            if captcha_detected:
                logger.warning("[placer] CAPTCHA appeared after entering credentials (%s)", captcha_type)
                self._report_progress(
                    "login", 100,
                    f"CAPTCHA ({captcha_type}) detected. Please use manual session refresh."
                )
                await self._save_debug_screenshot(page, "placer_captcha_after_creds.png")
                return False

            self._report_progress("login", 50, "Submitting login...")

            # Click submit
            submit_clicked = False
            for selector in submit_selectors:
                if await self._safe_click(page, selector, timeout_ms=3000):
                    submit_clicked = True
                    break

            if not submit_clicked:
                await page.keyboard.press("Enter")

            # Wait for navigation after login
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(2000)  # Extra wait for SPA to settle

            self._report_progress("login", 80, "Verifying login...")

            logger.debug("[placer] After login navigation complete")

            # Check for CAPTCHA challenge after submit (common scenario)
            captcha_detected, captcha_type = await self._detect_captcha(page)
            if captcha_detected:
                logger.warning("[placer] CAPTCHA challenge appeared after submit (%s)", captcha_type)
                self._report_progress(
                    "login", 100,
                    f"CAPTCHA challenge ({captcha_type}) blocked login. Please use manual session refresh."
                )
                await self._save_debug_screenshot(page, "placer_captcha_after_submit.png")
                return False

            # Check for successful login
            is_logged_in = await self._check_logged_in_state(page)

            if is_logged_in:
                self._report_progress("login", 100, "Login successful!")
                return True

            # Take screenshot for debugging
            await self._save_debug_screenshot(page, "placer_login_debug.png")

            # Check for error messages
            error_selectors = [
                ".error-message",
                ".alert-error",
                ".alert-danger",
                '[role="alert"]',
                '[class*="error"]',
                '[data-testid="error-message"]',
            ]

            for selector in error_selectors:
                error_elements = await page.query_selector_all(selector)
                for error_el in error_elements:
                    try:
                        error_text = await error_el.inner_text()
                        if error_text.strip():
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

    async def login_with_captcha_detection(
        self,
        context: BrowserContext,
        username: str,
        password: str,
    ) -> LoginResult:
        """
        Attempt login with detailed CAPTCHA detection for Placer.ai.

        This is the preferred login method as it provides detailed information
        about CAPTCHA blocking, which is common for Placer.ai.

        Returns:
            LoginResult with detailed status about CAPTCHA and login success
        """
        page = await context.new_page()
        screenshot_path = None

        try:
            self._report_progress("login", 5, "Navigating to Placer.ai login...")
            await page.goto(f"{self.site_url}/auth/signin", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # Check for CAPTCHA on initial page load
            captcha_detected, captcha_type = await self._detect_captcha(page)

            if captcha_detected:
                screenshot_path = await self._save_debug_screenshot(
                    page, "placer_captcha_initial.png"
                )
                self._report_progress(
                    "login", 100,
                    f"CAPTCHA ({captcha_type}) detected - manual login required"
                )
                return LoginResult(
                    success=False,
                    message=f"Placer.ai requires solving a {captcha_type} CAPTCHA. Please use manual session refresh to log in.",
                    captcha_detected=True,
                    captcha_type=captcha_type,
                    requires_manual_login=True,
                    error_type="captcha",
                    screenshot_path=screenshot_path,
                )

            # Try to fill credentials
            self._report_progress("login", 20, "Entering credentials...")

            email_selectors = [
                '[data-testid="email-input-field"]',
                'input[name="username"]',
                'input[placeholder*="company.com"]',
                'input[type="text"]',
            ]

            password_selectors = [
                '[data-testid="login-password-input"]',
                'input[name="password"]',
                'input[type="password"]',
            ]

            # Fill email
            email_filled = False
            for selector in email_selectors:
                if await self._safe_fill(page, selector, username, timeout_ms=3000):
                    email_filled = True
                    break

            if not email_filled:
                screenshot_path = await self._save_debug_screenshot(
                    page, "placer_no_email_field.png"
                )
                return LoginResult(
                    success=False,
                    message="Could not find email field on login page",
                    error_type="page_structure",
                    screenshot_path=screenshot_path,
                )

            # Fill password
            password_filled = False
            for selector in password_selectors:
                if await self._safe_fill(page, selector, password, timeout_ms=3000):
                    password_filled = True
                    break

            if not password_filled:
                screenshot_path = await self._save_debug_screenshot(
                    page, "placer_no_password_field.png"
                )
                return LoginResult(
                    success=False,
                    message="Could not find password field on login page",
                    error_type="page_structure",
                    screenshot_path=screenshot_path,
                )

            # Check for CAPTCHA after filling credentials
            await page.wait_for_timeout(500)
            captcha_detected, captcha_type = await self._detect_captcha(page)

            if captcha_detected:
                screenshot_path = await self._save_debug_screenshot(
                    page, "placer_captcha_after_creds.png"
                )
                self._report_progress(
                    "login", 100,
                    f"CAPTCHA ({captcha_type}) appeared - manual login required"
                )
                return LoginResult(
                    success=False,
                    message=f"CAPTCHA ({captcha_type}) appeared after entering credentials. Please use manual session refresh.",
                    captcha_detected=True,
                    captcha_type=captcha_type,
                    requires_manual_login=True,
                    error_type="captcha",
                    screenshot_path=screenshot_path,
                )

            self._report_progress("login", 50, "Submitting login...")

            # Click submit
            submit_selectors = [
                '[data-testid="login-page-login-button"]',
                'button[type="submit"]',
                'button:has-text("Login")',
            ]

            submit_clicked = False
            for selector in submit_selectors:
                if await self._safe_click(page, selector, timeout_ms=3000):
                    submit_clicked = True
                    break

            if not submit_clicked:
                await page.keyboard.press("Enter")

            # Wait for response
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            self._report_progress("login", 80, "Verifying login...")

            # Check for CAPTCHA challenge after submit
            captcha_detected, captcha_type = await self._detect_captcha(page)

            if captcha_detected:
                screenshot_path = await self._save_debug_screenshot(
                    page, "placer_captcha_after_submit.png"
                )
                return LoginResult(
                    success=False,
                    message=f"CAPTCHA challenge ({captcha_type}) blocked login. Please use manual session refresh.",
                    captcha_detected=True,
                    captcha_type=captcha_type,
                    requires_manual_login=True,
                    error_type="captcha",
                    screenshot_path=screenshot_path,
                )

            # Check if logged in
            is_logged_in = await self._check_logged_in_state(page)

            if is_logged_in:
                self._report_progress("login", 100, "Login successful!")
                return LoginResult(
                    success=True,
                    message="Login successful",
                )

            # Login failed - check for error messages
            screenshot_path = await self._save_debug_screenshot(
                page, "placer_login_failed.png"
            )

            error_selectors = [
                ".error-message",
                ".alert-error",
                ".alert-danger",
                '[role="alert"]',
                '[class*="error"]',
            ]

            for selector in error_selectors:
                error_elements = await page.query_selector_all(selector)
                for error_el in error_elements:
                    try:
                        error_text = (await error_el.inner_text()).strip()
                        if error_text:
                            return LoginResult(
                                success=False,
                                message=f"Login failed: {error_text}",
                                error_type="invalid_credentials",
                                screenshot_path=screenshot_path,
                            )
                    except Exception:
                        continue

            return LoginResult(
                success=False,
                message="Login failed - please verify your credentials",
                error_type="invalid_credentials",
                screenshot_path=screenshot_path,
            )

        except PlaywrightTimeout:
            screenshot_path = await self._save_debug_screenshot(
                page, "placer_login_timeout.png"
            )
            return LoginResult(
                success=False,
                message="Login timed out - Placer.ai may be slow or unavailable",
                error_type="timeout",
                screenshot_path=screenshot_path,
            )
        except Exception as e:
            screenshot_path = await self._save_debug_screenshot(
                page, "placer_login_error.png"
            )
            return LoginResult(
                success=False,
                message=f"Login error: {str(e)}",
                error_type="network",
                screenshot_path=screenshot_path,
            )
        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def _check_logged_in_state(self, page: Page) -> bool:
        """Check if we're logged in to Placer.ai."""
        url = page.url.lower()

        # Still on auth pages means not logged in
        if "/auth/signin" in url or "/auth/signup" in url:
            return False

        # Check URL patterns that indicate logged-in state
        logged_in_patterns = ["/dashboard", "/explore", "/venues", "/insights", "/home", "/places"]
        if any(pattern in url for pattern in logged_in_patterns):
            return True

        # Check for UI elements that indicate logged-in state
        logged_in_selectors = [
            '[data-testid="user-menu"]',
            '[data-testid="user-avatar"]',
            '[data-testid="sidebar"]',
            ".user-profile",
            ".user-menu",
            'button:has-text("Logout")',
            'button:has-text("Sign Out")',
            'a[href*="logout"]',
            '[class*="sidebar"]',
            '[class*="MainSidebar"]',
        ]

        for selector in logged_in_selectors:
            if await page.query_selector(selector):
                return True

        return False

    async def is_logged_in(self, context: BrowserContext) -> bool:
        """Check if current session is logged in."""
        page = await context.new_page()

        try:
            await page.goto(self.site_url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # If redirected to auth/signin, not logged in
            if "/auth/signin" in page.url.lower() or "/auth/signup" in page.url.lower():
                return False

            return await self._check_logged_in_state(page)
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
        """Scrape data from Placer.ai."""
        start_time = time.time()

        try:
            if data_type == DataType.VISITOR_TRAFFIC:
                result = await self._scrape_visitor_traffic(context, params)
            elif data_type == DataType.CUSTOMER_PROFILE:
                result = await self._scrape_customer_profile(context, params)
            elif data_type == DataType.VOID_ANALYSIS:
                result = await self._scrape_void_analysis(context, params)
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

    async def _search_venue(self, page: Page, address: str) -> bool:
        """Search for a venue by address and navigate to its page."""
        self._report_progress("search", 20, f"Searching for {address}...")

        # Navigate to search/explore page
        search_urls = [
            f"{self.site_url}/#!/explore",
            f"{self.site_url}/#!/places",
            f"{self.site_url}/#!/dashboard",
        ]

        navigated = False
        for url in search_urls:
            try:
                await page.goto(url, wait_until="networkidle", timeout=15000)
                await page.wait_for_timeout(2000)
                navigated = True
                break
            except Exception:
                continue

        if not navigated:
            # Try the base URL which should redirect to dashboard
            await page.goto(self.site_url, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)

        # Find and fill search input
        search_selectors = [
            'input[type="search"]',
            'input[placeholder*="search" i]',
            'input[placeholder*="address" i]',
            'input[placeholder*="venue" i]',
            'input[data-testid="search-input"]',
            '[role="searchbox"]',
            ".search-input input",
        ]

        search_filled = False
        for selector in search_selectors:
            if await self._safe_fill(page, selector, address, timeout_ms=5000):
                search_filled = True
                break

        if not search_filled:
            return False

        # Trigger search
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)  # Wait for results

        # Click on first result
        result_selectors = [
            '[data-testid="search-result"]:first-child',
            ".search-result:first-child",
            ".venue-result:first-child",
            '[class*="result"]:first-child',
            ".autocomplete-item:first-child",
        ]

        for selector in result_selectors:
            if await self._safe_click(page, selector, timeout_ms=5000):
                await page.wait_for_load_state("networkidle", timeout=15000)
                return True

        # If no clickable result, check if we're already on venue page
        await page.wait_for_timeout(2000)
        return "/venue" in page.url.lower() or "/place" in page.url.lower()

    async def _scrape_visitor_traffic(
        self,
        context: BrowserContext,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """Scrape visitor traffic data from Placer.ai."""
        address = params.get("address")

        if not address:
            return ScrapeResult(success=False, error="Address is required")

        page = await context.new_page()

        try:
            # Search and navigate to venue
            if not await self._search_venue(page, address):
                return ScrapeResult(
                    success=False,
                    error=f"Could not find venue: {address}",
                )

            self._report_progress("scrape", 40, "Loading traffic data...")

            # Navigate to foot traffic section if needed
            traffic_selectors = [
                'a:has-text("Traffic")',
                'button:has-text("Traffic")',
                '[data-testid="traffic-tab"]',
                'a[href*="traffic"]',
            ]

            for selector in traffic_selectors:
                if await self._safe_click(page, selector, timeout_ms=3000):
                    await page.wait_for_timeout(2000)
                    break

            self._report_progress("scrape", 60, "Extracting traffic metrics...")

            # Extract foot traffic data
            data = await self._extract_foot_traffic_data(page)

            if not data or not any(v for k, v in data.items() if k != "source"):
                return ScrapeResult(
                    success=False,
                    error="Could not extract foot traffic data",
                )

            self._report_progress("scrape", 100, "Complete!")
            return ScrapeResult(success=True, data=data)

        except PlaywrightTimeout:
            return ScrapeResult(success=False, error="Request timed out")
        except Exception as e:
            return ScrapeResult(success=False, error=str(e))
        finally:
            await page.close()

    async def _extract_foot_traffic_data(self, page: Page) -> dict[str, Any]:
        """Extract foot traffic metrics from the page."""
        data = {}

        # Common label patterns for foot traffic metrics
        metric_mappings = {
            "monthly_visitors": [
                "Monthly Visits",
                "Monthly Visitors",
                "Visits (Monthly)",
                "Total Visits",
            ],
            "daily_avg_visitors": [
                "Daily Average",
                "Avg. Daily Visits",
                "Daily Visitors",
                "Visits per Day",
            ],
            "vehicles_per_day": [
                "VPD",
                "Vehicles Per Day",
                "Daily Vehicles",
                "Vehicle Count",
            ],
            "peak_day": [
                "Peak Day",
                "Busiest Day",
                "Top Day",
            ],
            "peak_hour": [
                "Peak Hour",
                "Busiest Hour",
                "Peak Time",
            ],
            "year_over_year_change_pct": [
                "YoY Change",
                "Year over Year",
                "YoY Growth",
                "Annual Change",
            ],
            "avg_dwell_time_minutes": [
                "Dwell Time",
                "Avg. Dwell",
                "Average Dwell Time",
                "Time Spent",
            ],
            "visitor_radius_miles": [
                "Trade Area",
                "Visitor Radius",
                "Travel Distance",
            ],
        }

        for field_key, labels in metric_mappings.items():
            for label in labels:
                value = await self._get_text_by_label(page, label)
                if value:
                    # Parse numeric values
                    cleaned = (
                        value.replace(",", "")
                        .replace("%", "")
                        .replace("mi", "")
                        .replace("min", "")
                        .replace("minutes", "")
                        .strip()
                    )
                    try:
                        if "." in cleaned:
                            data[field_key] = float(cleaned)
                        else:
                            data[field_key] = int(cleaned)
                    except ValueError:
                        data[field_key] = value
                    break

        # Try to get venue name
        venue_name = await self._get_text(page, "h1, .venue-name, [data-testid='venue-name']")
        if venue_name:
            data["venue_name"] = venue_name

        data["source"] = "Placer.ai"
        return data

    async def _scrape_customer_profile(
        self,
        context: BrowserContext,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """Scrape customer profile / audience overview from Placer.ai."""
        address = params.get("address")

        if not address:
            return ScrapeResult(success=False, error="Address is required")

        page = await context.new_page()

        try:
            if not await self._search_venue(page, address):
                return ScrapeResult(
                    success=False,
                    error=f"Could not find venue: {address}",
                )

            self._report_progress("scrape", 40, "Loading audience data...")

            # Navigate to audience/demographics section
            audience_selectors = [
                'a:has-text("Audience")',
                'a:has-text("Demographics")',
                'a:has-text("Customer")',
                'button:has-text("Audience")',
                '[data-testid="audience-tab"]',
                'a[href*="audience"]',
                'a[href*="demographics"]',
            ]

            for selector in audience_selectors:
                if await self._safe_click(page, selector, timeout_ms=3000):
                    await page.wait_for_timeout(2000)
                    break

            self._report_progress("scrape", 60, "Extracting customer profile...")

            data = await self._extract_customer_profile_data(page)

            if not data or not any(v for k, v in data.items() if k != "source"):
                return ScrapeResult(
                    success=False,
                    error="Could not extract customer profile data",
                )

            self._report_progress("scrape", 100, "Complete!")
            return ScrapeResult(success=True, data=data)

        except PlaywrightTimeout:
            return ScrapeResult(success=False, error="Request timed out")
        except Exception as e:
            return ScrapeResult(success=False, error=str(e))
        finally:
            await page.close()

    async def _extract_customer_profile_data(self, page: Page) -> dict[str, Any]:
        """Extract customer profile / audience demographics from the page."""
        data = {}

        metric_mappings = {
            "median_household_income": [
                "Median HH Income",
                "Median Household Income",
                "HH Income",
                "Household Income",
            ],
            "median_age": [
                "Median Age",
                "Average Age",
                "Visitor Age",
            ],
            "male_pct": [
                "Male",
                "% Male",
                "Male %",
            ],
            "female_pct": [
                "Female",
                "% Female",
                "Female %",
            ],
            "age_18_24_pct": ["18-24", "Ages 18-24"],
            "age_25_34_pct": ["25-34", "Ages 25-34"],
            "age_35_44_pct": ["35-44", "Ages 35-44"],
            "age_45_54_pct": ["45-54", "Ages 45-54"],
            "age_55_plus_pct": ["55+", "55 and over", "Ages 55+"],
            "bachelors_degree_pct": [
                "Bachelor's",
                "College Degree",
                "Bachelor's Degree",
            ],
            "avg_household_size": [
                "Household Size",
                "HH Size",
                "Avg. HH Size",
            ],
        }

        for field_key, labels in metric_mappings.items():
            for label in labels:
                value = await self._get_text_by_label(page, label)
                if value:
                    cleaned = (
                        value.replace(",", "")
                        .replace("%", "")
                        .replace("$", "")
                        .replace("k", "000")
                        .replace("K", "000")
                        .strip()
                    )
                    try:
                        if "." in cleaned:
                            data[field_key] = float(cleaned)
                        else:
                            data[field_key] = int(cleaned)
                    except ValueError:
                        data[field_key] = value
                    break

        # Get venue info
        venue_name = await self._get_text(page, "h1, .venue-name, [data-testid='venue-name']")
        if venue_name:
            data["venue_name"] = venue_name

        data["source"] = "Placer.ai"
        return data

    async def _scrape_void_analysis(
        self,
        context: BrowserContext,
        params: dict[str, Any],
    ) -> ScrapeResult:
        """Scrape void analysis / missing tenant categories from Placer.ai."""
        address = params.get("address")

        if not address:
            return ScrapeResult(success=False, error="Address is required")

        page = await context.new_page()

        try:
            if not await self._search_venue(page, address):
                return ScrapeResult(
                    success=False,
                    error=f"Could not find venue: {address}",
                )

            self._report_progress("scrape", 40, "Loading void analysis...")

            # Navigate to void/gap analysis section
            void_selectors = [
                'a:has-text("Void")',
                'a:has-text("Gap Analysis")',
                'a:has-text("Opportunities")',
                'a:has-text("Missing")',
                'button:has-text("Void")',
                '[data-testid="void-tab"]',
                'a[href*="void"]',
                'a[href*="gap"]',
            ]

            for selector in void_selectors:
                if await self._safe_click(page, selector, timeout_ms=3000):
                    await page.wait_for_timeout(2000)
                    break

            self._report_progress("scrape", 60, "Extracting void opportunities...")

            data = await self._extract_void_analysis_data(page)

            if not data.get("voids"):
                return ScrapeResult(
                    success=False,
                    error="Could not extract void analysis data",
                )

            self._report_progress("scrape", 100, "Complete!")
            return ScrapeResult(success=True, data=data)

        except PlaywrightTimeout:
            return ScrapeResult(success=False, error="Request timed out")
        except Exception as e:
            return ScrapeResult(success=False, error=str(e))
        finally:
            await page.close()

    async def _extract_void_analysis_data(self, page: Page) -> dict[str, Any]:
        """Extract void analysis / gap opportunities from the page."""
        voids = []

        # Try to find void/opportunity items in various formats
        item_selectors = [
            ".void-item",
            ".gap-item",
            ".opportunity-item",
            '[data-testid="void-opportunity"]',
            "tr.void-row",
            ".tenant-opportunity",
        ]

        for selector in item_selectors:
            items = await page.query_selector_all(selector)
            if items:
                for item in items[:20]:  # Limit to 20 items
                    void = await self._extract_single_void(item)
                    if void:
                        voids.append(void)
                break

        # If no structured items found, try to parse from tables
        if not voids:
            tables = await page.query_selector_all("table")
            for table in tables:
                rows = await table.query_selector_all("tr")
                for row in rows[1:]:  # Skip header row
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 2:
                        try:
                            tenant_name = (await cells[0].inner_text()).strip()
                            category = (
                                (await cells[1].inner_text()).strip()
                                if len(cells) > 1
                                else ""
                            )
                            distance = None
                            match_score = None

                            if len(cells) > 2:
                                dist_text = (await cells[2].inner_text()).strip()
                                try:
                                    distance = float(
                                        dist_text.replace("mi", "").replace(",", "").strip()
                                    )
                                except ValueError:
                                    pass

                            if len(cells) > 3:
                                score_text = (await cells[3].inner_text()).strip()
                                try:
                                    match_score = float(score_text.replace("%", "").strip())
                                except ValueError:
                                    pass

                            if tenant_name:
                                voids.append(
                                    {
                                        "tenant_name": tenant_name,
                                        "category": category,
                                        "distance_miles": distance,
                                        "match_score": match_score,
                                    }
                                )
                        except Exception:
                            continue

        return {
            "voids": voids,
            "total_count": len(voids),
            "source": "Placer.ai",
        }

    async def _extract_single_void(self, element) -> dict[str, Any] | None:
        """Extract a single void opportunity from an element."""
        try:
            tenant_name = await self._get_text(
                element, ".tenant-name, .name, [data-testid='tenant-name']"
            )
            if not tenant_name:
                tenant_name = (await element.inner_text()).split("\n")[0].strip()

            if not tenant_name:
                return None

            category = await self._get_text(
                element, ".category, .type, [data-testid='category']"
            )
            distance_text = await self._get_text(
                element, ".distance, .miles, [data-testid='distance']"
            )
            score_text = await self._get_text(
                element, ".score, .match-score, [data-testid='match-score']"
            )

            distance = None
            if distance_text:
                try:
                    distance = float(
                        distance_text.replace("mi", "").replace(",", "").strip()
                    )
                except ValueError:
                    pass

            match_score = None
            if score_text:
                try:
                    match_score = float(score_text.replace("%", "").strip())
                except ValueError:
                    pass

            return {
                "tenant_name": tenant_name,
                "category": category or "",
                "distance_miles": distance,
                "match_score": match_score,
            }
        except Exception:
            return None

    async def _get_text(
        self,
        parent,
        selector: str,
        default: str = "",
    ) -> str:
        """Safely get text content from an element within a parent."""
        try:
            element = await parent.query_selector(selector)
            if element:
                text = await element.inner_text()
                return text.strip()
        except Exception:
            pass
        return default
