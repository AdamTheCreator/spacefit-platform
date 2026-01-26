"""
Security and compliance enforcement for the Connector Platform.

Responsibilities:
- Domain allowlist enforcement
- Runtime limits (max time, max nav steps, max content size)
- Per-tenant session isolation (delegated to BrowserManager)
- Secret redaction in logs / traces
"""

from __future__ import annotations

import re
import logging
from urllib.parse import urlparse

from app.connectors.schemas.errors import ConnectorError, ErrorCode, ErrorSeverity
from app.connectors.schemas.manifest import ConnectorManifest

logger = logging.getLogger("connectors.security")

# Pattern for things that look like secrets
_SECRET_PATTERN = re.compile(
    r"(password|secret|token|api_key|apikey|authorization|credential)"
    r"\s*[:=]\s*\S+",
    re.IGNORECASE,
)


class SecurityEnforcer:
    """
    Guards for a single connector execution.

    Created per-execution with the connector's manifest limits, then
    called by the workflow runner at each step boundary.
    """

    def __init__(self, manifest: ConnectorManifest) -> None:
        self._manifest = manifest
        self._allowed_domains = [d.lower() for d in manifest.allowed_domains]
        self._max_runtime = manifest.runtime_limits.max_runtime_seconds
        self._max_nav_steps = manifest.runtime_limits.max_navigation_steps
        self._max_bytes = manifest.runtime_limits.max_extracted_bytes

    # ------------------------------------------------------------------
    # Domain enforcement
    # ------------------------------------------------------------------

    def check_domain(self, url: str) -> None:
        """Raise if *url*'s host is not on the allowlist."""
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not any(host == d or host.endswith(f".{d}") for d in self._allowed_domains):
            raise ConnectorError(
                code=ErrorCode.SEC_DOMAIN_BLOCKED,
                message=f"Navigation to '{host}' blocked. Allowed: {self._allowed_domains}",
                severity=ErrorSeverity.PERMANENT,
                remediation="Add the domain to the connector manifest's allowed_domains.",
            )

    # ------------------------------------------------------------------
    # Runtime limits
    # ------------------------------------------------------------------

    def check_runtime(self, elapsed_seconds: float) -> None:
        if elapsed_seconds > self._max_runtime:
            raise ConnectorError(
                code=ErrorCode.SEC_RUNTIME_EXCEEDED,
                message=(
                    f"Execution exceeded max runtime of {self._max_runtime}s "
                    f"(elapsed: {elapsed_seconds:.1f}s)."
                ),
                severity=ErrorSeverity.PERMANENT,
                remediation="Narrow the query or increase runtime_limits.max_runtime_seconds.",
            )

    def check_nav_steps(self, steps: int) -> None:
        if steps >= self._max_nav_steps:
            raise ConnectorError(
                code=ErrorCode.SEC_NAV_LIMIT_EXCEEDED,
                message=f"Navigation step limit reached ({self._max_nav_steps}).",
                severity=ErrorSeverity.PERMANENT,
                remediation="Simplify the workflow or increase runtime_limits.max_navigation_steps.",
            )

    def check_content_limit(self, bytes_extracted: int) -> None:
        if bytes_extracted > self._max_bytes:
            raise ConnectorError(
                code=ErrorCode.SEC_CONTENT_LIMIT_EXCEEDED,
                message=f"Extracted content exceeds limit ({self._max_bytes} bytes).",
                severity=ErrorSeverity.PERMANENT,
                remediation="Narrow the extraction scope or increase runtime_limits.max_extracted_bytes.",
            )

    # ------------------------------------------------------------------
    # Secret redaction
    # ------------------------------------------------------------------

    @staticmethod
    def redact(text: str) -> str:
        """Replace anything that looks like a secret with [REDACTED]."""
        return _SECRET_PATTERN.sub("[REDACTED]", text)

    @staticmethod
    def redact_dict(d: dict) -> dict:
        """
        Return a shallow copy of *d* with secret-looking keys replaced
        by '[REDACTED]'.
        """
        sensitive_keys = {
            "password", "secret", "token", "api_key", "apikey",
            "authorization", "credential", "access_token", "refresh_token",
        }
        out = {}
        for k, v in d.items():
            if k.lower() in sensitive_keys:
                out[k] = "[REDACTED]"
            elif isinstance(v, str) and len(v) > 20 and any(
                s in k.lower() for s in ("key", "secret", "token", "pass")
            ):
                out[k] = "[REDACTED]"
            else:
                out[k] = v
        return out
