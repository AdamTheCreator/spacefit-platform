"""
API Runner.

Executes HTTP-based workflow steps using httpx.  Handles pagination,
JSON parsing, rate-limit back-off, and response extraction.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.connectors.schemas.errors import (
    ConnectorError,
    ErrorCode,
    ErrorSeverity,
)
from app.connectors.runner.steps import StepType, WorkflowStep
from app.connectors.telemetry import ConnectorTelemetry

logger = logging.getLogger("connectors.runner.api")


class APIRunner:
    """Stateless runner for API-mode workflow steps."""

    def __init__(
        self,
        allowed_domains: list[str],
        default_headers: dict[str, str] | None = None,
        timeout_seconds: int = 30,
        telemetry: ConnectorTelemetry | None = None,
    ) -> None:
        self._allowed_domains = [d.lower() for d in allowed_domains]
        self._default_headers = default_headers or {}
        self._timeout = timeout_seconds
        self._tel = telemetry
        self._api_calls = 0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def run_step(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a single API step and return updated context.
        """
        if step.step_type == StepType.HTTP_REQUEST:
            return await self._http_request(step, context)
        if step.step_type == StepType.PARSE_JSON:
            return self._parse_json(step, context)
        if step.step_type == StepType.PAGINATE:
            return await self._paginate(step, context)
        if step.step_type == StepType.SET_VAR:
            return self._set_var(step, context)
        if step.step_type == StepType.LOG:
            self._log(step, context)
            return context

        raise ConnectorError(
            code=ErrorCode.PLATFORM_WORKFLOW_ERROR,
            message=f"APIRunner cannot handle step type: {step.step_type}",
        )

    @property
    def api_calls_made(self) -> int:
        return self._api_calls

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _http_request(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        url = self._interpolate(step.url or "", context)
        self._enforce_domain(url)

        headers = {**self._default_headers, **step.headers}
        headers = {k: self._interpolate(v, context) for k, v in headers.items()}

        body = step.body
        if body:
            body = {
                k: self._interpolate(v, context) if isinstance(v, str) else v
                for k, v in body.items()
            }

        method = step.method.upper()
        timeout = step.timeout_ms / 1000

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method, url, headers=headers, json=body if method != "GET" else None,
                    params=body if method == "GET" and body else None,
                )
            elapsed_ms = int((time.monotonic() - t0) * 1000)
        except httpx.TimeoutException as exc:
            raise ConnectorError(
                code=ErrorCode.NET_TIMEOUT,
                message=f"HTTP {method} {url} timed out after {timeout}s",
                severity=ErrorSeverity.TRANSIENT,
                remediation="Retry with backoff.",
            ) from exc
        except httpx.ConnectError as exc:
            raise ConnectorError(
                code=ErrorCode.NET_CONNECTION_REFUSED,
                message=f"Connection refused: {url}",
                severity=ErrorSeverity.TRANSIENT,
            ) from exc

        self._api_calls += 1

        if self._tel:
            self._tel.record_api_call(url, method, resp.status_code, elapsed_ms)

        # Handle rate-limiting
        if resp.status_code == 429:
            raise ConnectorError(
                code=ErrorCode.NET_RATE_LIMITED,
                message=f"Rate limited by {url}",
                severity=ErrorSeverity.TRANSIENT,
                remediation="Retry after cooldown.",
            )

        if resp.status_code >= 500:
            raise ConnectorError(
                code=ErrorCode.NET_SERVER_ERROR,
                message=f"Server error {resp.status_code} from {url}",
                severity=ErrorSeverity.TRANSIENT,
            )

        if resp.status_code >= 400:
            raise ConnectorError(
                code=ErrorCode.NET_CONNECTION_REFUSED,
                message=f"HTTP {resp.status_code} from {url}: {resp.text[:500]}",
                severity=ErrorSeverity.PERMANENT,
            )

        # Store response
        output_key = step.output_key or "_last_response"
        context[output_key] = resp.text
        context["_last_status"] = resp.status_code
        context["_last_headers"] = dict(resp.headers)

        # Auto-parse JSON if content type is application/json
        ct = resp.headers.get("content-type", "")
        if "json" in ct:
            try:
                context[f"{output_key}_json"] = resp.json()
            except Exception:
                pass

        return context

    def _parse_json(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        import json

        source_key = step.value or "_last_response"
        raw = context.get(source_key, "")
        output_key = step.output_key or "_parsed"

        try:
            context[output_key] = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError) as exc:
            raise ConnectorError(
                code=ErrorCode.EXTRACT_PARSE_FAILURE,
                message=f"JSON parse error: {exc}",
            ) from exc

        return context

    async def _paginate(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Follow pagination.  Expects context to contain a 'next_url' or
        'next_token' set by a previous step.  Aggregates results into
        a list under step.output_key.
        """
        results: list[Any] = context.get(step.output_key or "_paginated", [])
        max_pages = 20  # safety cap

        for _ in range(max_pages):
            next_url = context.get("_next_url")
            if not next_url:
                break

            page_step = WorkflowStep(
                step_type=StepType.HTTP_REQUEST,
                url=next_url,
                method=step.method,
                headers=step.headers,
                output_key="_page_response",
            )
            context = await self._http_request(page_step, context)

            page_data = context.get("_page_response_json", {})
            if isinstance(page_data, dict):
                items = page_data.get("results", page_data.get("data", []))
                results.extend(items if isinstance(items, list) else [items])
                context["_next_url"] = page_data.get("next") or page_data.get("next_url")
            else:
                break

        context[step.output_key or "_paginated"] = results
        context.pop("_next_url", None)
        return context

    @staticmethod
    def _set_var(step: WorkflowStep, context: dict[str, Any]) -> dict[str, Any]:
        if step.output_key and step.value is not None:
            context[step.output_key] = step.value
        return context

    @staticmethod
    def _log(step: WorkflowStep, context: dict[str, Any]) -> None:
        msg = step.value or ""
        logger.info("[workflow] %s", msg)

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
                severity=ErrorSeverity.PERMANENT,
            )

    @staticmethod
    def _interpolate(template: str, context: dict[str, Any]) -> str:
        """Simple {{variable}} interpolation against context."""
        import re

        def replacer(m: re.Match) -> str:
            key = m.group(1).strip()
            return str(context.get(key, m.group(0)))

        return re.sub(r"\{\{(.+?)\}\}", replacer, template)
