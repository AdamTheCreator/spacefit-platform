"""
Browser Runner.

Executes browser-based workflow steps using the existing Playwright
BrowserManager.  Supports the full step vocabulary: open, snapshot,
click, type, wait, extract, download, state_save, state_load, scroll.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page

from app.connectors.schemas.errors import (
    ConnectorError,
    ErrorCode,
    ErrorSeverity,
)
from app.connectors.runner.steps import StepType, WorkflowStep
from app.connectors.security import SecurityEnforcer
from app.connectors.telemetry import ConnectorTelemetry

logger = logging.getLogger("connectors.runner.browser")


class BrowserRunner:
    """
    Interprets browser workflow steps against a Playwright BrowserContext.
    """

    def __init__(
        self,
        context: BrowserContext,
        allowed_domains: list[str],
        *,
        security: SecurityEnforcer | None = None,
        telemetry: ConnectorTelemetry | None = None,
        sessions_dir: str = "./browser_sessions",
    ) -> None:
        self._context = context
        self._allowed_domains = [d.lower() for d in allowed_domains]
        self._security = security
        self._tel = telemetry
        self._sessions_dir = Path(sessions_dir)
        self._page: Page | None = None
        self._pages_visited: list[str] = []
        self._nav_steps = 0
        self._bytes_extracted = 0
        self._artifacts: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def run_step(
        self,
        step: WorkflowStep,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one browser workflow step, return updated context."""
        handler = self._handlers.get(step.step_type)
        if handler is None:
            raise ConnectorError(
                code=ErrorCode.PLATFORM_WORKFLOW_ERROR,
                message=f"BrowserRunner cannot handle step type: {step.step_type}",
            )
        return await handler(self, step, ctx)

    @property
    def pages_visited(self) -> list[str]:
        return list(self._pages_visited)

    @property
    def nav_steps(self) -> int:
        return self._nav_steps

    @property
    def bytes_extracted(self) -> int:
        return self._bytes_extracted

    @property
    def artifacts(self) -> dict[str, str]:
        return dict(self._artifacts)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _open(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        url = self._interpolate(step.url or "", ctx)
        self._enforce_domain(url)
        self._nav_steps += 1

        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()

        await self._page.goto(url, wait_until="domcontentloaded", timeout=step.timeout_ms)
        self._pages_visited.append(url)

        if self._tel:
            self._tel.record_page_visit(url)

        return ctx

    async def _snapshot(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        if not self._page:
            return ctx
        path = f"/tmp/snapshot_{int(time.time())}.png"
        await self._page.screenshot(path=path, full_page=True)
        self._artifacts["snapshot"] = path

        # Also capture accessibility tree text for agent-browser pattern
        try:
            tree = await self._page.accessibility.snapshot()
            ctx["_accessibility_tree"] = tree
        except Exception:
            pass

        return ctx

    async def _click(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        if not self._page:
            return ctx
        self._nav_steps += 1

        selector = self._interpolate(step.selector or step.ref or "", ctx)
        try:
            await self._page.click(selector, timeout=step.timeout_ms)
        except Exception as exc:
            raise ConnectorError(
                code=ErrorCode.EXTRACT_LAYOUT_CHANGED,
                message=f"Click failed on selector '{selector}': {exc}",
                severity=ErrorSeverity.PERMANENT,
                remediation="Selector may have changed; update the workflow.",
            ) from exc
        return ctx

    async def _type(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        if not self._page:
            return ctx
        selector = self._interpolate(step.selector or step.ref or "", ctx)
        value = self._interpolate(step.value or "", ctx)
        try:
            await self._page.fill(selector, value, timeout=step.timeout_ms)
        except Exception as exc:
            raise ConnectorError(
                code=ErrorCode.EXTRACT_LAYOUT_CHANGED,
                message=f"Type failed on selector '{selector}': {exc}",
            ) from exc
        return ctx

    async def _wait(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        if not self._page:
            return ctx
        wait_for = step.wait_for or "networkidle"

        if wait_for == "networkidle":
            await self._page.wait_for_load_state("networkidle", timeout=step.timeout_ms)
        elif wait_for.startswith("url:"):
            pattern = wait_for[4:]
            await self._page.wait_for_url(f"**{pattern}**", timeout=step.timeout_ms)
        elif wait_for.startswith("selector:"):
            sel = wait_for[9:]
            await self._page.wait_for_selector(sel, timeout=step.timeout_ms)
        else:
            # Treat as selector
            await self._page.wait_for_selector(wait_for, timeout=step.timeout_ms)

        return ctx

    async def _extract(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        if not self._page:
            return ctx

        extract_type = step.extract_type or "text"
        selector = self._interpolate(step.extract_selector or step.selector or "body", ctx)
        output_key = step.output_key or "_extracted"

        if extract_type == "text":
            el = await self._page.query_selector(selector)
            if el:
                text = await el.inner_text()
                ctx[output_key] = text.strip()
                self._bytes_extracted += len(text.encode())
            else:
                ctx[output_key] = ""

        elif extract_type == "structured":
            # Extract all matching elements as a list of text values
            elements = await self._page.query_selector_all(selector)
            items = []
            for el in elements:
                text = await el.inner_text()
                items.append(text.strip())
                self._bytes_extracted += len(text.encode())
            ctx[output_key] = items

        elif extract_type == "table":
            # Extract HTML table as list of dicts
            rows = await self._page.evaluate("""(selector) => {
                const table = document.querySelector(selector);
                if (!table) return [];
                const headers = Array.from(table.querySelectorAll('th'))
                    .map(th => th.innerText.trim());
                return Array.from(table.querySelectorAll('tbody tr')).map(row => {
                    const cells = Array.from(row.querySelectorAll('td'))
                        .map(td => td.innerText.trim());
                    const obj = {};
                    headers.forEach((h, i) => { obj[h] = cells[i] || ''; });
                    return obj;
                });
            }""", selector)
            ctx[output_key] = rows
            self._bytes_extracted += len(str(rows).encode())

        elif extract_type == "json":
            # Extract page text and parse as JSON
            import json as json_mod
            el = await self._page.query_selector(selector)
            if el:
                raw = await el.inner_text()
                try:
                    ctx[output_key] = json_mod.loads(raw)
                except json_mod.JSONDecodeError:
                    ctx[output_key] = raw
                self._bytes_extracted += len(raw.encode())

        if self._security:
            self._security.check_content_limit(self._bytes_extracted)

        return ctx

    async def _download(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        if not self._page:
            return ctx
        selector = self._interpolate(step.selector or "", ctx)

        async with self._page.expect_download(timeout=step.timeout_ms) as dl_info:
            await self._page.click(selector)
        download = await dl_info.value
        dest = f"/tmp/{download.suggested_filename}"
        await download.save_as(dest)
        ctx[step.output_key or "_download_path"] = dest
        self._artifacts["download"] = dest
        return ctx

    async def _state_save(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        tenant_id = ctx.get("_tenant_id", "default")
        connector_id = ctx.get("_connector_id", "unknown")
        path = self._sessions_dir / f"{tenant_id}_{connector_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=str(path))
        ctx["_session_path"] = str(path)
        return ctx

    async def _state_load(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        # State loading is handled at context creation time by BrowserManager.
        # This step is a no-op during execution but signals intent in the workflow.
        return ctx

    async def _scroll(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        if not self._page:
            return ctx
        direction = step.value or "down"
        if direction == "down":
            await self._page.evaluate("window.scrollBy(0, window.innerHeight)")
        elif direction == "up":
            await self._page.evaluate("window.scrollBy(0, -window.innerHeight)")
        elif direction == "bottom":
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        return ctx

    async def _set_var(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        if step.output_key and step.value is not None:
            ctx[step.output_key] = self._interpolate(step.value, ctx)
        return ctx

    async def _log(self, step: WorkflowStep, ctx: dict[str, Any]) -> dict[str, Any]:
        msg = self._interpolate(step.value or "", ctx)
        logger.info("[browser-workflow] %s", msg)
        return ctx

    # ------------------------------------------------------------------
    # Debug artifacts
    # ------------------------------------------------------------------

    async def capture_failure_artifacts(self) -> dict[str, str]:
        """Capture screenshot + console errors on failure."""
        artifacts: dict[str, str] = {}
        if self._page and not self._page.is_closed():
            try:
                path = f"/tmp/failure_{int(time.time())}.png"
                await self._page.screenshot(path=path, full_page=True)
                artifacts["failure_screenshot"] = path
            except Exception:
                pass
        return artifacts

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        if self._page and not self._page.is_closed():
            await self._page.close()
            self._page = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _enforce_domain(self, url: str) -> None:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or ""
        if not any(
            host == d or host.endswith(f".{d}") for d in self._allowed_domains
        ):
            raise ConnectorError(
                code=ErrorCode.SEC_DOMAIN_BLOCKED,
                message=f"Domain '{host}' is not in the allowlist: {self._allowed_domains}",
            )

    @staticmethod
    def _interpolate(template: str, ctx: dict[str, Any]) -> str:
        import re

        def replacer(m: re.Match) -> str:
            key = m.group(1).strip()
            return str(ctx.get(key, m.group(0)))

        return re.sub(r"\{\{(.+?)\}\}", replacer, template)

    # ------------------------------------------------------------------
    # Handler dispatch table
    # ------------------------------------------------------------------

    _handlers: dict = {}  # populated below


# Build handler map
BrowserRunner._handlers = {
    StepType.OPEN: BrowserRunner._open,
    StepType.SNAPSHOT: BrowserRunner._snapshot,
    StepType.CLICK: BrowserRunner._click,
    StepType.TYPE: BrowserRunner._type,
    StepType.WAIT: BrowserRunner._wait,
    StepType.EXTRACT: BrowserRunner._extract,
    StepType.DOWNLOAD: BrowserRunner._download,
    StepType.STATE_SAVE: BrowserRunner._state_save,
    StepType.STATE_LOAD: BrowserRunner._state_load,
    StepType.SCROLL: BrowserRunner._scroll,
    StepType.SET_VAR: BrowserRunner._set_var,
    StepType.LOG: BrowserRunner._log,
}
