"""
Test SitesUSA REGIS login with credentials.
Run with: python -m scripts.test_siteusa_login <username> <password>
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright


async def test_login(username: str, password: str):
    """Test login to SitesUSA REGIS."""

    print("Launching browser (visible mode)...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context()
        page = await context.new_page()

        login_url = "https://regis.sitesusa.com/login"
        print(f"\n1. Navigating to: {login_url}")
        await page.goto(login_url, wait_until="networkidle")
        print(f"   Current URL: {page.url}")

        # Wait for page to fully load
        await page.wait_for_timeout(1000)

        print("\n2. Filling username...")
        username_field = await page.query_selector('#mat-input-0')
        if username_field:
            await username_field.fill(username)
            print("   Username filled")
        else:
            print("   ERROR: Could not find username field")
            await browser.close()
            return

        print("\n3. Filling password...")
        password_field = await page.query_selector('#mat-input-1')
        if password_field:
            await password_field.fill(password)
            print("   Password filled")
        else:
            print("   ERROR: Could not find password field")
            await browser.close()
            return

        print("\n4. Clicking Sign In...")
        submit_btn = await page.query_selector('button[type="submit"]')
        if submit_btn:
            await submit_btn.click()
            print("   Clicked submit")
        else:
            print("   ERROR: Could not find submit button")
            await browser.close()
            return

        # Wait for navigation
        print("\n5. Waiting for response...")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        current_url = page.url
        print(f"   Current URL: {current_url}")

        # Check for success or error
        if "/login" not in current_url.lower():
            print("\n✓ SUCCESS! Redirected away from login page.")
            await page.screenshot(path="siteusa_logged_in.png")
            print("   Screenshot saved: siteusa_logged_in.png")
        else:
            print("\n✗ FAILED - Still on login page")

            # Check for error messages
            error_selectors = [
                '.mat-error',
                '.error-message',
                '[class*="error"]',
                'mat-error',
            ]

            for selector in error_selectors:
                errors = await page.query_selector_all(selector)
                for err in errors:
                    text = await err.inner_text()
                    if text.strip():
                        print(f"   Error message: {text.strip()}")

            await page.screenshot(path="siteusa_login_failed.png")
            print("   Screenshot saved: siteusa_login_failed.png")

        print("\nBrowser will close in 10 seconds...")
        await asyncio.sleep(10)
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.test_siteusa_login <username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    asyncio.run(test_login(username, password))
