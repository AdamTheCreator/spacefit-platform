"""
Generic Workflow Runner.

Orchestrates execution of a WorkflowDefinition by delegating each step
to either the APIRunner or BrowserRunner based on step type and the
connector's execution mode.  Handles retries, security enforcement,
and telemetry collection.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import yaml

from app.connectors.runner.steps import (
    StepType,
    WorkflowDefinition,
    WorkflowStep,
)
from app.connectors.runner.api_runner import APIRunner
from app.connectors.runner.browser_runner import BrowserRunner
from app.connectors.schemas.errors import (
    ConnectorError,
    ErrorCode,
    ErrorSeverity,
)
from app.connectors.schemas.manifest import ConnectorManifest, ExecutionMode
from app.connectors.schemas.response import (
    ConnectorResponse,
    ErrorDetail,
    Metrics,
    Provenance,
    ResponseStatus,
)
from app.connectors.schemas.task import TaskRequest
from app.connectors.security import SecurityEnforcer
from app.connectors.telemetry import ConnectorTelemetry

logger = logging.getLogger("connectors.runner")

# Steps that should be handled by the browser runner
_BROWSER_STEPS = {
    StepType.OPEN, StepType.SNAPSHOT, StepType.CLICK, StepType.TYPE,
    StepType.WAIT, StepType.EXTRACT, StepType.DOWNLOAD, StepType.SCROLL,
    StepType.STATE_SAVE, StepType.STATE_LOAD,
}

# Steps that should be handled by the API runner
_API_STEPS = {
    StepType.HTTP_REQUEST, StepType.PARSE_JSON, StepType.PAGINATE,
}

# Steps handled by the workflow runner itself
_CONTROL_STEPS = {
    StepType.CONDITION, StepType.LOOP, StepType.SET_VAR, StepType.LOG,
}


class WorkflowRunner:
    """
    Drives a WorkflowDefinition to completion, composing API and browser
    runners as needed.
    """

    def __init__(
        self,
        manifest: ConnectorManifest,
        *,
        api_runner: APIRunner | None = None,
        browser_runner: BrowserRunner | None = None,
        security: SecurityEnforcer | None = None,
        telemetry: ConnectorTelemetry | None = None,
    ) -> None:
        self._manifest = manifest
        self._api_runner = api_runner
        self._browser_runner = browser_runner
        self._security = security or SecurityEnforcer(manifest)
        self._tel = telemetry or ConnectorTelemetry(manifest.connector_id)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def run(
        self,
        request: TaskRequest,
        workflow: WorkflowDefinition,
        initial_context: dict[str, Any] | None = None,
    ) -> ConnectorResponse:
        """
        Execute all steps in *workflow*, collect metrics, and return a
        ConnectorResponse envelope.
        """
        ctx: dict[str, Any] = {
            **(workflow.variables or {}),
            **(initial_context or {}),
            **(request.params or {}),
            "_tenant_id": request.tenant_id,
            "_connector_id": self._manifest.connector_id,
            "_task_id": request.task_id,
            "_trace_id": request.trace_id,
        }

        started_at = time.monotonic()
        errors: list[ErrorDetail] = []
        steps_executed = 0

        self._tel.start_trace(request.trace_id, request.task_id)

        try:
            for step in workflow.steps:
                self._security.check_runtime(time.monotonic() - started_at)
                ctx = await self._execute_step(step, ctx)
                steps_executed += 1

        except ConnectorError as exc:
            self._tel.record_error(exc)
            errors.append(ErrorDetail(
                code=exc.code.value,
                message=exc.message,
                severity=exc.severity.value,
                remediation=exc.remediation,
                details=exc.details,
            ))

            # Capture debug artifacts on failure
            debug_artifacts = {}
            if self._browser_runner:
                debug_artifacts = await self._browser_runner.capture_failure_artifacts()

            elapsed_ms = int((time.monotonic() - started_at) * 1000)

            status = (
                ResponseStatus.USER_ACTION_REQUIRED
                if exc.severity == ErrorSeverity.USER_ACTION
                else ResponseStatus.FAILURE
            )

            return ConnectorResponse(
                task_id=request.task_id,
                trace_id=request.trace_id,
                status=status,
                data=None,
                provenance=self._build_provenance(steps_executed),
                metrics=self._build_metrics(elapsed_ms),
                errors=errors,
                debug_artifacts=debug_artifacts,
            )

        except Exception as exc:
            logger.exception("Unexpected error in workflow runner")
            errors.append(ErrorDetail(
                code=ErrorCode.PLATFORM_INTERNAL.value,
                message=str(exc),
                severity="error",
                remediation="Check platform logs with trace_id.",
            ))
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            return ConnectorResponse(
                task_id=request.task_id,
                trace_id=request.trace_id,
                status=ResponseStatus.FAILURE,
                provenance=self._build_provenance(steps_executed),
                metrics=self._build_metrics(elapsed_ms),
                errors=errors,
            )

        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        self._tel.finish_trace(success=True, latency_ms=elapsed_ms)

        # Extract the final data from context
        data = ctx.get("_result") or ctx.get("_extracted") or ctx.get("_parsed")

        return ConnectorResponse(
            task_id=request.task_id,
            trace_id=request.trace_id,
            status=ResponseStatus.SUCCESS,
            data=data,
            provenance=self._build_provenance(steps_executed),
            metrics=self._build_metrics(elapsed_ms),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Load workflow from YAML
    # ------------------------------------------------------------------

    @staticmethod
    def load_workflow(path: str | Path) -> WorkflowDefinition:
        """Load a WorkflowDefinition from a YAML file."""
        path = Path(path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return WorkflowDefinition(**raw)

    # ------------------------------------------------------------------
    # Step dispatch
    # ------------------------------------------------------------------

    async def _execute_step(
        self,
        step: WorkflowStep,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        """Route a step to the correct runner."""

        if step.step_type in _CONTROL_STEPS:
            return await self._run_control(step, ctx)

        if step.step_type in _BROWSER_STEPS:
            if self._browser_runner is None:
                raise ConnectorError(
                    code=ErrorCode.PLATFORM_WORKFLOW_ERROR,
                    message=f"Browser step '{step.step_type}' but no BrowserRunner configured.",
                )
            if self._security:
                self._security.check_nav_steps(
                    self._browser_runner.nav_steps
                )
            return await self._browser_runner.run_step(step, ctx)

        if step.step_type in _API_STEPS:
            if self._api_runner is None:
                raise ConnectorError(
                    code=ErrorCode.PLATFORM_WORKFLOW_ERROR,
                    message=f"API step '{step.step_type}' but no APIRunner configured.",
                )
            return await self._api_runner.run_step(step, ctx)

        raise ConnectorError(
            code=ErrorCode.PLATFORM_WORKFLOW_ERROR,
            message=f"Unknown step type: {step.step_type}",
        )

    async def _run_control(
        self,
        step: WorkflowStep,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        if step.step_type == StepType.SET_VAR:
            if step.output_key and step.value is not None:
                ctx[step.output_key] = self._interpolate(step.value, ctx)
            return ctx

        if step.step_type == StepType.LOG:
            msg = self._interpolate(step.value or "", ctx)
            logger.info("[workflow:%s] %s", self._manifest.connector_id, msg)
            return ctx

        if step.step_type == StepType.CONDITION:
            if step.condition and step.sub_steps:
                try:
                    result = eval(step.condition, {"__builtins__": {}}, ctx)  # noqa: S307
                except Exception:
                    result = False
                if result:
                    for sub in step.sub_steps:
                        ctx = await self._execute_step(sub, ctx)
            return ctx

        if step.step_type == StepType.LOOP:
            if step.loop_over and step.sub_steps:
                items = ctx.get(step.loop_over, [])
                loop_var = step.loop_as or "_item"
                for item in items:
                    ctx[loop_var] = item
                    for sub in step.sub_steps:
                        ctx = await self._execute_step(sub, ctx)
            return ctx

        return ctx

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_provenance(self, steps_executed: int) -> Provenance:
        pages = self._browser_runner.pages_visited if self._browser_runner else []
        return Provenance(
            source_connector=self._manifest.connector_id,
            execution_mode=self._manifest.preferred_mode.value,
            pages_visited=pages,
            workflow_steps_executed=steps_executed,
        )

    def _build_metrics(self, elapsed_ms: int) -> Metrics:
        return Metrics(
            latency_ms=elapsed_ms,
            pages_visited=self._browser_runner.nav_steps if self._browser_runner else 0,
            bytes_extracted=self._browser_runner.bytes_extracted if self._browser_runner else 0,
            api_calls_made=self._api_runner.api_calls_made if self._api_runner else 0,
        )

    @staticmethod
    def _interpolate(template: str, ctx: dict[str, Any]) -> str:
        import re

        def replacer(m: re.Match) -> str:
            key = m.group(1).strip()
            return str(ctx.get(key, m.group(0)))

        return re.sub(r"\{\{(.+?)\}\}", replacer, template)
