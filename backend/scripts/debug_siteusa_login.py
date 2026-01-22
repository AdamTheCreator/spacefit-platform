"""
Debug script to inspect SitesUSA REGIS login page and capture selectors.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright


async def debug_siteusa_login():
    """Open SitesUSA login page and inspect it."""

    print("Launching browser (visible mode)...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context()
        page = await context.new_page()

        login_url = "https://regis.sitesusa.com/login"
        print(f"Navigating to: {login_url}")
        await page.goto(login_url, wait_until="networkidle")

        # Take screenshot
        await page.screenshot(path="siteusa_login.png")
        print(f"Screenshot saved: siteusa_login.png")
        print(f"Current URL: {page.url}")

        # Wait a moment for any JS to load
        await page.wait_for_timeout(2000)

        # Inspect the page for form elements
        print("\n" + "="*60)
        print("INSPECTING LOGIN PAGE")
        print("="*60)

        # Find all input fields
        inputs = await page.query_selector_all("input")
        print(f"\nFound {len(inputs)} input fields:")
        for inp in inputs:
            inp_type = await inp.get_attribute("type") or "text"
            inp_name = await inp.get_attribute("name") or ""
            inp_id = await inp.get_attribute("id") or ""
            inp_placeholder = await inp.get_attribute("placeholder") or ""
            inp_class = await inp.get_attribute("class") or ""
            visible = await inp.is_visible()
            print(f"  - type='{inp_type}', name='{inp_name}', id='{inp_id}', placeholder='{inp_placeholder}', visible={visible}")
            if inp_class:
                print(f"    class='{inp_class[:80]}...'")

        # Find all buttons
        buttons = await page.query_selector_all("button, input[type='submit'], a.btn, a.button")
        print(f"\nFound {len(buttons)} buttons/links:")
        for btn in buttons:
            tag = await btn.evaluate("el => el.tagName")
            btn_text = ""
            try:
                btn_text = (await btn.inner_text()).strip()
            except:
                pass
            btn_type = await btn.get_attribute("type") or ""
            btn_class = await btn.get_attribute("class") or ""
            visible = await btn.is_visible()
            print(f"  - <{tag}> '{btn_text[:30]}' type='{btn_type}' visible={visible}")
            if btn_class:
                print(f"    class='{btn_class[:60]}...'")

        # Check for forms
        forms = await page.query_selector_all("form")
        print(f"\nFound {len(forms)} forms:")
        for i, form in enumerate(forms):
            action = await form.get_attribute("action") or ""
            method = await form.get_attribute("method") or ""
            form_id = await form.get_attribute("id") or ""
            print(f"  Form {i+1}: action='{action}', method='{method}', id='{form_id}'")

        # Check for iframes (login might be in an iframe)
        iframes = await page.query_selector_all("iframe")
        print(f"\nFound {len(iframes)} iframes:")
        for iframe in iframes:
            src = await iframe.get_attribute("src") or ""
            print(f"  - src='{src[:80]}...'")

        # Get page title
        title = await page.title()
        print(f"\nPage title: {title}")

        # Get a snippet of the page HTML
        body_html = await page.evaluate("document.body.innerHTML")
        print(f"\nPage HTML snippet (first 2000 chars):")
        print(body_html[:2000])

        print("\n" + "="*60)
        print("Browser will stay open for 30 seconds for manual inspection.")
        print("="*60)

        try:
            await asyncio.sleep(30)
        except KeyboardInterrupt:
            pass

        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_siteusa_login())
