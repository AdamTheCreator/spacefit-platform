"""
Interactive browser login service for CAPTCHA-protected sites.

This service opens a visible browser window for the user to complete login
manually (including CAPTCHA solving), then captures the session cookies.

For production deployment options:
1. Local/Self-hosted: Browser window opens on server machine
2. Desktop app (Electron): Browser window opens locally
3. Cloud: Use browser streaming service (Browserless.io, etc.)
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class LoginStatus(str, Enum):
    """Status of the interactive login process."""
    INITIALIZING = "initializing"
    BROWSER_OPENING = "browser_opening"
    NAVIGATING = "navigating"
    WAITING_FOR_LOGIN = "waiting_for_login"
    LOGIN_DETECTED = "login_detected"
    SAVING_SESSION = "saving_session"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class LoginStatusUpdate:
    """Status update for the login process."""
    status: LoginStatus
    message: str
    progress_pct: int  # 0-100
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "message": self.message,
            "progress_pct": self.progress_pct,
            "timestamp": self.timestamp.isoformat(),
        }


StatusCallback = Callable[[LoginStatusUpdate], Any]


class InteractiveLoginManager:
    """
    Manages interactive browser login sessions for CAPTCHA-protected sites.

    Usage:
        manager = InteractiveLoginManager(
            site_name="placer",
            user_id="user123",
            status_callback=my_callback,
        )
        result = await manager.start_login(
            login_url="https://analytics.placer.ai/auth/signin",
            success_url_patterns=["/dashboard", "/explore"],
        )
    """

    def __init__(
        self,
        site_name: str,
        user_id: str,
        sessions_dir: str = "./browser_sessions",
        status_callback: StatusCallback | None = None,
    ):
        self.site_name = site_name
        self.user_id = user_id
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(exist_ok=True)
        self.status_callback = status_callback

        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._cancelled = False

    def _report_status(self, status: LoginStatus, message: str, progress: int):
        """Report status update via callback."""
        update = LoginStatusUpdate(
            status=status,
            message=message,
            progress_pct=progress,
        )
        if self.status_callback:
            # Handle both sync and async callbacks
            result = self.status_callback(update)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
        return update

    @property
    def session_file_path(self) -> Path:
        """Path to the session storage file."""
        safe_user_id = "".join(c if c.isalnum() else "_" for c in self.user_id)[:20]
        return self.sessions_dir / f"{safe_user_id}_{self.site_name}.json"

    async def start_login(
        self,
        login_url: str,
        success_url_patterns: list[str],
        timeout_seconds: int = 300,
        prefill_username: str | None = None,
        prefill_password: str | None = None,
    ) -> LoginStatusUpdate:
        """
        Start an interactive login session.

        Opens a visible browser window for the user to complete login.
        Monitors for successful login and captures session cookies.

        Args:
            login_url: URL of the login page
            success_url_patterns: URL patterns that indicate successful login
            timeout_seconds: Maximum time to wait for login (default 5 minutes)
            prefill_username: Optional username to prefill
            prefill_password: Optional password to prefill

        Returns:
            Final LoginStatusUpdate indicating success or failure
        """
        self._cancelled = False

        try:
            # Initialize browser
            self._report_status(
                LoginStatus.INITIALIZING,
                "Preparing secure browser session...",
                5
            )

            playwright = await async_playwright().start()

            self._report_status(
                LoginStatus.BROWSER_OPENING,
                "Opening browser window...",
                10
            )

            # Launch visible browser
            self._browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            # Create context with realistic settings
            self._context = await self._browser.new_context(
                viewport={"width": 1200, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            self._page = await self._context.new_page()

            # Navigate to login page
            self._report_status(
                LoginStatus.NAVIGATING,
                "Loading login page...",
                20
            )

            await self._page.goto(login_url, wait_until="networkidle")
            await self._page.wait_for_timeout(1000)

            # Prefill credentials if provided
            if prefill_username or prefill_password:
                await self._prefill_credentials(prefill_username, prefill_password)

            # Wait for user to complete login
            self._report_status(
                LoginStatus.WAITING_FOR_LOGIN,
                "Please complete login in the browser window. Solve any CAPTCHA that appears.",
                30
            )

            # Monitor for successful login
            login_success = await self._wait_for_login(
                success_url_patterns,
                timeout_seconds,
            )

            if self._cancelled:
                return self._report_status(
                    LoginStatus.CANCELLED,
                    "Login cancelled by user",
                    100
                )

            if not login_success:
                return self._report_status(
                    LoginStatus.TIMEOUT,
                    f"Login timed out after {timeout_seconds} seconds. Please try again.",
                    100
                )

            # Login detected - save session
            self._report_status(
                LoginStatus.LOGIN_DETECTED,
                "Login successful! Saving session...",
                80
            )

            self._report_status(
                LoginStatus.SAVING_SESSION,
                "Securely storing session cookies...",
                90
            )

            # Save session state
            await self._save_session()

            return self._report_status(
                LoginStatus.SUCCESS,
                "Session saved successfully! You can close this window.",
                100
            )

        except Exception as e:
            return self._report_status(
                LoginStatus.FAILED,
                f"Login failed: {str(e)}",
                100
            )
        finally:
            # Keep browser open briefly so user sees success message
            if self._page and not self._cancelled:
                try:
                    await self._page.wait_for_timeout(2000)
                except Exception:
                    pass

            await self._cleanup()

    async def _prefill_credentials(
        self,
        username: str | None,
        password: str | None,
    ):
        """Prefill login credentials if provided."""
        if not self._page:
            return

        # Common username field selectors
        username_selectors = [
            'input[type="email"]',
            'input[type="text"][name*="user"]',
            'input[type="text"][name*="email"]',
            'input[placeholder*="email" i]',
            'input[placeholder*="user" i]',
        ]

        # Common password field selectors
        password_selectors = [
            'input[type="password"]',
        ]

        if username:
            for selector in username_selectors:
                try:
                    field = await self._page.query_selector(selector)
                    if field and await field.is_visible():
                        await field.fill(username)
                        break
                except Exception:
                    continue

        if password:
            for selector in password_selectors:
                try:
                    field = await self._page.query_selector(selector)
                    if field and await field.is_visible():
                        await field.fill(password)
                        break
                except Exception:
                    continue

    async def _wait_for_login(
        self,
        success_patterns: list[str],
        timeout_seconds: int,
    ) -> bool:
        """Wait for user to complete login."""
        if not self._page:
            return False

        check_interval = 1  # Check every second
        elapsed = 0

        while elapsed < timeout_seconds and not self._cancelled:
            await self._page.wait_for_timeout(check_interval * 1000)
            elapsed += check_interval

            # Check URL for success patterns
            current_url = self._page.url.lower()

            # Skip if still on login page
            if "/auth/signin" in current_url or "/login" in current_url:
                # Update progress periodically
                if elapsed % 10 == 0:
                    self._report_status(
                        LoginStatus.WAITING_FOR_LOGIN,
                        f"Waiting for login... ({elapsed}s)",
                        30 + min(40, elapsed // 6)  # Progress from 30-70%
                    )
                continue

            # Check for success patterns
            for pattern in success_patterns:
                if pattern.lower() in current_url:
                    return True

            # Also check for common logged-in indicators
            logged_in_selectors = [
                '[data-testid="user-menu"]',
                '.user-menu',
                '.user-avatar',
                'button[aria-label*="account" i]',
                '[class*="sidebar"]',
            ]

            for selector in logged_in_selectors:
                try:
                    element = await self._page.query_selector(selector)
                    if element:
                        return True
                except Exception:
                    continue

        return False

    async def _save_session(self):
        """Save the browser session state."""
        if not self._context:
            return

        storage_state = await self._context.storage_state()

        with open(self.session_file_path, "w") as f:
            json.dump(storage_state, f, indent=2)

    async def _cleanup(self):
        """Clean up browser resources."""
        try:
            if self._page:
                await self._page.close()
        except Exception:
            pass

        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass

        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass

        self._page = None
        self._context = None
        self._browser = None

    def cancel(self):
        """Cancel the login process."""
        self._cancelled = True


# Site-specific configurations
SITE_LOGIN_CONFIGS = {
    "placer": {
        "login_url": "https://analytics.placer.ai/auth/signin",
        "success_url_patterns": ["/dashboard", "/explore", "/venues", "/insights", "/home", "/places"],
        "display_name": "Placer.ai",
    },
    "siteusa": {
        "login_url": "https://regis.sitesusa.com/login",
        "success_url_patterns": ["/dashboard", "/search", "/reports"],
        "display_name": "SitesUSA REGIS",
    },
    "costar": {
        "login_url": "https://www.costar.com/login",
        "success_url_patterns": ["/home", "/search", "/property"],
        "display_name": "CoStar",
    },
}


def get_site_login_config(site_name: str) -> dict | None:
    """Get login configuration for a site."""
    return SITE_LOGIN_CONFIGS.get(site_name.lower())


async def start_interactive_login(
    site_name: str,
    user_id: str,
    status_callback: StatusCallback | None = None,
    prefill_username: str | None = None,
    prefill_password: str | None = None,
    timeout_seconds: int = 300,
) -> LoginStatusUpdate:
    """
    Convenience function to start an interactive login session.

    Args:
        site_name: Name of the site (e.g., "placer", "siteusa")
        user_id: User ID for session storage
        status_callback: Optional callback for status updates
        prefill_username: Optional username to prefill
        prefill_password: Optional password to prefill
        timeout_seconds: Maximum time to wait for login

    Returns:
        Final LoginStatusUpdate
    """
    config = get_site_login_config(site_name)
    if not config:
        return LoginStatusUpdate(
            status=LoginStatus.FAILED,
            message=f"Unknown site: {site_name}",
            progress_pct=100,
        )

    manager = InteractiveLoginManager(
        site_name=site_name,
        user_id=user_id,
        status_callback=status_callback,
    )

    return await manager.start_login(
        login_url=config["login_url"],
        success_url_patterns=config["success_url_patterns"],
        timeout_seconds=timeout_seconds,
        prefill_username=prefill_username,
        prefill_password=prefill_password,
    )
