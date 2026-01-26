"""
ConnectorPlatform — the top-level façade.

Sub-agents interact exclusively with this class.  It wires together the
registry, router, secrets, security, telemetry, and workflow runner to
provide a single `execute()` entry point.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.interface import BaseConnector
from app.connectors.registry import ConnectorRegistry
from app.connectors.router import ConnectorRouter, RouteCandidate
from app.connectors.runner.api_runner import APIRunner
from app.connectors.runner.browser_runner import BrowserRunner
from app.connectors.runner.workflow_runner import WorkflowRunner
from app.connectors.schemas.errors import (
    ConnectorError,
    ErrorCode,
    ErrorSeverity,
)
from app.connectors.schemas.manifest import ExecutionMode
from app.connectors.schemas.response import (
    ConnectorResponse,
    ErrorDetail,
    ResponseStatus,
)
from app.connectors.schemas.task import TaskRequest
from app.connectors.secrets import SecretManager
from app.connectors.security import SecurityEnforcer
from app.connectors.telemetry import ConnectorTelemetry, metrics_store, retry_with_backoff

logger = logging.getLogger("connectors.platform")


class ConnectorPlatform:
    """
    Top-level entry point for the Connector Platform.

    Usage:
        platform = ConnectorPlatform()
        platform.load_connectors("connector_manifests")

        response = await platform.execute(request, db=db_session)
    """

    def __init__(self) -> None:
        self._registry = ConnectorRegistry.get_instance()
        self._router = ConnectorRouter(self._registry)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def load_connectors(self, directory: str | Path) -> int:
        """Load all connector manifests from *directory*."""
        return self._registry.load_directory(directory)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        request: TaskRequest,
        *,
        db: AsyncSession | None = None,
        user_connector_ids: list[str] | None = None,
        browser_context: Any | None = None,
    ) -> ConnectorResponse:
        """
        Execute a task request end-to-end:
          1. Route to the best connector
          2. Load secrets
          3. Authenticate
          4. Execute (via workflow runner or direct)
          5. Normalize
          6. Return response envelope
        """

        # --- Route ---
        try:
            candidate = self._router.select(
                request, user_connector_ids=user_connector_ids
            )
        except ConnectorError as exc:
            return self._error_response(request, exc)

        manifest = candidate.manifest
        mode = candidate.mode
        telemetry = ConnectorTelemetry(manifest.connector_id)
        telemetry.start_trace(request.trace_id, request.task_id)

        # --- Create connector instance ---
        connector = self._registry.create_connector(manifest.connector_id)

        try:
            # --- Validate config ---
            await connector.validate_config()

            # --- Authenticate ---
            if request.credential_id and db:
                secret_mgr = SecretManager(db)
                creds = await secret_mgr.get_credentials(
                    request.credential_id, request.tenant_id
                )
                await connector.authenticate(creds, tenant_id=request.tenant_id)

            # --- Execute ---
            async def _do_execute() -> ConnectorResponse:
                return await connector.execute(request)

            response = await retry_with_backoff(
                _do_execute,
                max_retries=2,
                telemetry=telemetry,
            )

            # --- Record metrics ---
            metrics_store.record_execution(
                connector_id=manifest.connector_id,
                success=response.status == ResponseStatus.SUCCESS,
                latency_ms=response.metrics.latency_ms,
            )

            return response

        except ConnectorError as exc:
            telemetry.record_error(exc)
            metrics_store.record_execution(
                connector_id=manifest.connector_id,
                success=False,
                latency_ms=0,
                auth_failure=exc.code.value.startswith("E1"),
                layout_changed=exc.code == ErrorCode.EXTRACT_LAYOUT_CHANGED,
            )
            return self._error_response(request, exc)

        except Exception as exc:
            logger.exception("Unhandled error in connector execution")
            metrics_store.record_execution(
                connector_id=manifest.connector_id,
                success=False,
                latency_ms=0,
            )
            return ConnectorResponse(
                task_id=request.task_id,
                trace_id=request.trace_id,
                status=ResponseStatus.FAILURE,
                errors=[ErrorDetail(
                    code=ErrorCode.PLATFORM_INTERNAL.value,
                    message=str(exc),
                    severity="error",
                    remediation="Check platform logs with trace_id.",
                )],
            )

        finally:
            await connector.teardown()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_connectors(self) -> list[dict[str, Any]]:
        """Return a summary of all registered connectors."""
        return [
            {
                "connector_id": m.connector_id,
                "name": m.name,
                "version": m.version,
                "capabilities": m.capabilities,
                "execution_modes": [e.value for e in m.execution_modes],
                "auth_type": m.auth_type.value,
            }
            for m in self._registry.list_connectors()
        ]

    def get_metrics(self, connector_id: str | None = None) -> dict:
        if connector_id:
            return metrics_store.get_stats(connector_id)
        return metrics_store.get_all_stats()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _error_response(request: TaskRequest, exc: ConnectorError) -> ConnectorResponse:
        status = (
            ResponseStatus.USER_ACTION_REQUIRED
            if exc.severity == ErrorSeverity.USER_ACTION
            else ResponseStatus.FAILURE
        )
        return ConnectorResponse(
            task_id=request.task_id,
            trace_id=request.trace_id,
            status=status,
            errors=[ErrorDetail(
                code=exc.code.value,
                message=exc.message,
                severity=exc.severity.value,
                remediation=exc.remediation,
                details=exc.details,
            )],
        )
