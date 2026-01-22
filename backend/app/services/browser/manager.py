"""
Browser automation manager using Playwright.
Provides pooled browser contexts with session persistence.
"""

import asyncio
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

from app.core.config import settings


class BrowserManager:
    """
    Singleton manager for Playwright browser instances.

    Features:
    - Single browser instance shared across contexts
    - Per-user session persistence (cookies, storage state)
    - Automatic cleanup on shutdown
    - Configurable headless/headed mode
    """

    _instance: Optional["BrowserManager"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: dict[str, BrowserContext] = {}
        self._sessions_dir = Path(settings.browser_sessions_dir)
        self._initialized = False

    @classmethod
    async def get_instance(cls) -> "BrowserManager":
        """Get or create the singleton instance."""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = BrowserManager()
            if not cls._instance._initialized:
                await cls._instance._initialize()
            return cls._instance

    async def _initialize(self) -> None:
        """Initialize Playwright and browser."""
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.browser_headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self._initialized = True

    def _get_storage_path(self, user_id: str, site_name: str) -> Path:
        """Get the storage state file path for a user/site combination."""
        safe_user_id = user_id.replace("-", "")[:16]
        safe_site = site_name.lower().replace(" ", "_")
        return self._sessions_dir / f"{safe_user_id}_{safe_site}.json"

    @asynccontextmanager
    async def get_context(
        self,
        user_id: str,
        site_name: str,
        load_session: bool = True,
    ):
        """
        Get a browser context for a user/site combination.

        Loads existing session state if available and load_session=True.
        Automatically saves state on exit.

        Usage:
            async with manager.get_context(user_id, "siteusa") as context:
                page = await context.new_page()
                await page.goto("https://siteusa.com")
        """
        if not self._browser:
            await self._initialize()

        context_key = f"{user_id}_{site_name}"
        storage_path = self._get_storage_path(user_id, site_name)

        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        if load_session and storage_path.exists():
            try:
                context_options["storage_state"] = str(storage_path)
            except Exception:
                pass

        context = await self._browser.new_context(**context_options)
        self._contexts[context_key] = context

        try:
            yield context
        finally:
            try:
                await context.storage_state(path=str(storage_path))
            except Exception:
                pass
            await context.close()
            self._contexts.pop(context_key, None)

    async def clear_session(self, user_id: str, site_name: str) -> bool:
        """Clear stored session for a user/site combination."""
        storage_path = self._get_storage_path(user_id, site_name)
        if storage_path.exists():
            storage_path.unlink()
            return True
        return False

    def has_session(self, user_id: str, site_name: str) -> bool:
        """Check if a session file exists for user/site."""
        storage_path = self._get_storage_path(user_id, site_name)
        return storage_path.exists()

    async def shutdown(self) -> None:
        """Clean up all resources."""
        for context in list(self._contexts.values()):
            try:
                await context.close()
            except Exception:
                pass
        self._contexts.clear()

        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._initialized = False

    @classmethod
    async def shutdown_instance(cls) -> None:
        """Shutdown the singleton instance if it exists."""
        if cls._instance:
            await cls._instance.shutdown()
            cls._instance = None
