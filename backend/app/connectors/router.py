"""
Connector Router.

Given a TaskRequest, selects the best connector to fulfil it based on:
  1. Required capability
  2. User's configured connectors (credentials)
  3. Execution mode preference (API > hybrid > browser)
  4. Ranking by confidence and cost
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.connectors.schemas.errors import ConnectorError, ErrorCode, ErrorSeverity
from app.connectors.schemas.manifest import ConnectorManifest, ExecutionMode
from app.connectors.schemas.task import TaskRequest
from app.connectors.registry import ConnectorRegistry

logger = logging.getLogger("connectors.router")


# Mode preference order — lower index = more preferred
_MODE_RANK: dict[ExecutionMode, int] = {
    ExecutionMode.API: 0,
    ExecutionMode.HYBRID: 1,
    ExecutionMode.BROWSER: 2,
}


@dataclass
class RouteCandidate:
    manifest: ConnectorManifest
    mode: ExecutionMode
    score: float  # Higher is better


class ConnectorRouter:
    """
    Stateless router that picks the best connector for a given task.
    """

    def __init__(
        self,
        registry: ConnectorRegistry | None = None,
    ) -> None:
        self._registry = registry or ConnectorRegistry.get_instance()

    def select(
        self,
        request: TaskRequest,
        *,
        user_connector_ids: list[str] | None = None,
    ) -> RouteCandidate:
        """
        Pick the best connector for *request*.

        Args:
            request: The incoming task.
            user_connector_ids: Connector IDs the user has configured
                credentials for.  If None, all registered connectors
                are eligible.

        Returns:
            A RouteCandidate with the chosen manifest and mode.

        Raises:
            ConnectorError if no suitable connector is found.
        """

        # 1. If explicit connector_id, just validate and return
        if request.connector_id:
            manifest = self._registry.get_manifest(request.connector_id)
            mode = self._resolve_mode(manifest, request.preferred_mode)
            return RouteCandidate(manifest=manifest, mode=mode, score=1.0)

        # 2. Find all connectors with the required capability
        candidates = self._registry.find_by_capability(request.capability)
        if not candidates:
            raise ConnectorError(
                code=ErrorCode.PLATFORM_NO_CAPABLE_CONNECTOR,
                message=f"No connector registered with capability '{request.capability}'.",
                severity=ErrorSeverity.PERMANENT,
                remediation="Register a connector with this capability.",
            )

        # 3. Filter to user's configured connectors
        if user_connector_ids is not None:
            id_set = set(user_connector_ids)
            candidates = [m for m in candidates if m.connector_id in id_set]
            if not candidates:
                raise ConnectorError(
                    code=ErrorCode.AUTH_MISSING_CREDENTIALS,
                    message=(
                        f"User has no configured connectors for capability "
                        f"'{request.capability}'."
                    ),
                    severity=ErrorSeverity.PERMANENT,
                    remediation="Add credentials for a connector with this capability.",
                )

        # 4. Score and rank
        scored: list[RouteCandidate] = []
        for manifest in candidates:
            mode = self._resolve_mode(manifest, request.preferred_mode)
            score = self._score(manifest, mode)
            scored.append(RouteCandidate(manifest=manifest, mode=mode, score=score))

        scored.sort(key=lambda c: c.score, reverse=True)

        winner = scored[0]
        logger.info(
            "Router selected connector=%s mode=%s score=%.2f for capability=%s "
            "(considered %d candidates)",
            winner.manifest.connector_id,
            winner.mode.value,
            winner.score,
            request.capability,
            len(scored),
        )
        return winner

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _score(manifest: ConnectorManifest, mode: ExecutionMode) -> float:
        """
        Heuristic score.  Higher = better.

        Factors:
        - Mode rank (API preferred over browser)
        - Rate limit generosity
        - Number of capabilities (prefer specialists)
        """
        score = 100.0

        # Prefer cheaper / faster execution modes
        mode_rank = _MODE_RANK.get(mode, 2)
        score -= mode_rank * 20  # API=100, hybrid=80, browser=60

        # Prefer connectors with higher rate limits (more headroom)
        score += min(manifest.rate_limit.requests_per_minute / 10, 10)

        # Slight preference for connectors with fewer capabilities (specialists)
        score -= len(manifest.capabilities) * 0.5

        return score

    @staticmethod
    def _resolve_mode(
        manifest: ConnectorManifest,
        preferred: str | None,
    ) -> ExecutionMode:
        """
        Determine the best execution mode for this connector.

        If the caller specifies a preferred mode and the connector supports
        it, use that.  Otherwise follow the default priority: API > hybrid > browser.
        """
        if preferred:
            try:
                pref_mode = ExecutionMode(preferred)
                if pref_mode in manifest.execution_modes:
                    return pref_mode
            except ValueError:
                pass

        # Follow platform-wide preference order
        for mode in (ExecutionMode.API, ExecutionMode.HYBRID, ExecutionMode.BROWSER):
            if mode in manifest.execution_modes:
                return mode

        return manifest.execution_modes[0]
