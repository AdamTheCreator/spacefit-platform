"""
Placer.ai Connector — Browser mode example.

Demonstrates a browser-based connector that:
  - Loads a persisted session (cookies from manual CAPTCHA login)
  - Executes a data-driven workflow defined in workflow.yaml
  - Falls back to user_action_required when CAPTCHA is detected
  - Normalizes extracted browser data into structured output
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from app.connectors.interface import BaseConnector
from app.connectors.runner.browser_runner import BrowserRunner
from app.connectors.runner.workflow_runner import WorkflowRunner
from app.connectors.schemas.errors import (
    ConnectorError,
    ErrorCode,
    ErrorSeverity,
)
from app.connectors.schemas.manifest import ConnectorManifest
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
from app.services.browser.manager import BrowserManager

logger = logging.getLogger("connectors.placer")


class PlacerConnector(BaseConnector):
    """
    Browser-mode connector for Placer.ai visitor traffic data.
    """

    def __init__(self, manifest: ConnectorManifest) -> None:
        super().__init__(manifest)
        self._browser_runner: BrowserRunner | None = None
        self._authenticated = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def validate_config(self) -> bool:
        if not self.manifest.workflow_file:
            raise ConnectorError(
                code=ErrorCode.PLATFORM_CONFIG_INVALID,
                message="Placer connector requires a workflow_file in its manifest.",
            )
        return True

    async def authenticate(
        self,
        credentials: dict[str, Any],
        *,
        tenant_id: str,
    ) -> bool:
        """
        For Placer.ai, authentication means verifying that a valid
        browser session exists.  If the session is expired or absent,
        we raise a user_action_required error (manual CAPTCHA login).
        """
        manager = await BrowserManager.get_instance()

        if not manager.has_session(tenant_id, "placer"):
            raise ConnectorError(
                code=ErrorCode.AUTH_CAPTCHA_REQUIRED,
                message="No active Placer.ai session found. Manual browser login required.",
                severity=ErrorSeverity.USER_ACTION,
                remediation="Complete manual browser login to solve CAPTCHA and create a session.",
            )

        self._authenticated = True
        return True

    async def execute(self, request: TaskRequest) -> ConnectorResponse:
        t0 = time.monotonic()
        telemetry = ConnectorTelemetry(self.manifest.connector_id)
        security = SecurityEnforcer(self.manifest)

        # Load workflow
        manifest_dir = Path(__file__).resolve().parent
        # Workflow lives alongside the manifest in connector_manifests/placer/
        workflow_path = (
            Path("connector_manifests") / "placer" / self.manifest.workflow_file
        )
        if not workflow_path.exists():
            # Fallback: look relative to this file's examples dir
            workflow_path = manifest_dir / self.manifest.workflow_file

        workflow = WorkflowRunner.load_workflow(workflow_path)

        # Get browser context
        manager = await BrowserManager.get_instance()

        try:
            async with manager.get_context(
                request.tenant_id, "placer", load_session=True
            ) as context:
                browser_runner = BrowserRunner(
                    context=context,
                    allowed_domains=self.manifest.allowed_domains,
                    security=security,
                    telemetry=telemetry,
                )
                self._browser_runner = browser_runner

                runner = WorkflowRunner(
                    manifest=self.manifest,
                    browser_runner=browser_runner,
                    security=security,
                    telemetry=telemetry,
                )

                response = await runner.run(
                    request,
                    workflow,
                    initial_context={"address": request.params.get("address", "")},
                )

                # Normalize if we got raw data
                if response.status == ResponseStatus.SUCCESS and response.data:
                    response.data = await self.normalize(response.data)

                return response

        except ConnectorError:
            raise
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("Placer connector execution failed")
            return ConnectorResponse(
                task_id=request.task_id,
                trace_id=request.trace_id,
                status=ResponseStatus.FAILURE,
                errors=[ErrorDetail(
                    code=ErrorCode.PLATFORM_INTERNAL.value,
                    message=str(exc),
                    severity="error",
                )],
                metrics=Metrics(latency_ms=elapsed_ms),
            )

    async def normalize(self, raw: Any) -> dict[str, Any] | list[Any]:
        """
        Transform raw browser-extracted data into the output schema.
        """
        if isinstance(raw, dict):
            return {
                "property_name": raw.get("property_name", ""),
                "visits": self._parse_traffic(raw),
                "customer_profile": raw.get("customer_profile", {}),
                "trade_area": raw.get("trade_area", {}),
                "raw_metrics": raw.get("traffic_metrics", []),
            }
        if isinstance(raw, str):
            return {"property_name": "", "raw_text": raw}
        return {"data": raw}

    async def teardown(self) -> None:
        if self._browser_runner:
            await self._browser_runner.close()
            self._browser_runner = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_traffic(raw: dict) -> dict[str, Any]:
        """Parse traffic metrics from extracted text."""
        metrics = raw.get("traffic_metrics", [])
        if isinstance(metrics, list) and metrics:
            # Attempt to parse numeric values from text
            values = []
            for m in metrics:
                cleaned = "".join(c for c in str(m) if c.isdigit() or c == ".")
                if cleaned:
                    try:
                        values.append(float(cleaned))
                    except ValueError:
                        pass

            return {
                "total": int(values[0]) if values else 0,
                "metrics_raw": metrics,
                "values_parsed": values,
            }
        return {"total": 0, "metrics_raw": metrics}
