"""
Error taxonomy for the Connector Platform.

Every error produced by the platform maps to an ErrorCode with a severity
level and a suggested remediation.  Sub-agents can use the error code to
decide whether to retry, fall back to another connector, or surface a
user-facing message.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ErrorSeverity(str, Enum):
    TRANSIENT = "transient"   # Retry is likely to succeed
    PERMANENT = "permanent"   # Retry will not help
    USER_ACTION = "user_action"  # Requires human intervention


class ErrorCode(str, Enum):
    # --- Auth errors (1xxx) ---
    AUTH_INVALID_CREDENTIALS = "E1001"
    AUTH_SESSION_EXPIRED = "E1002"
    AUTH_CAPTCHA_REQUIRED = "E1003"
    AUTH_2FA_REQUIRED = "E1004"
    AUTH_ACCOUNT_LOCKED = "E1005"
    AUTH_OAUTH_REFRESH_FAILED = "E1006"
    AUTH_MISSING_CREDENTIALS = "E1007"

    # --- Network / transient errors (2xxx) ---
    NET_TIMEOUT = "E2001"
    NET_CONNECTION_REFUSED = "E2002"
    NET_DNS_FAILURE = "E2003"
    NET_RATE_LIMITED = "E2004"
    NET_SERVER_ERROR = "E2005"

    # --- Extraction errors (3xxx) ---
    EXTRACT_LAYOUT_CHANGED = "E3001"
    EXTRACT_NO_DATA = "E3002"
    EXTRACT_PARSE_FAILURE = "E3003"
    EXTRACT_SCHEMA_MISMATCH = "E3004"

    # --- Security / policy errors (4xxx) ---
    SEC_DOMAIN_BLOCKED = "E4001"
    SEC_RUNTIME_EXCEEDED = "E4002"
    SEC_NAV_LIMIT_EXCEEDED = "E4003"
    SEC_CONTENT_LIMIT_EXCEEDED = "E4004"
    SEC_BOT_DETECTED = "E4005"

    # --- Platform errors (5xxx) ---
    PLATFORM_CONNECTOR_NOT_FOUND = "E5001"
    PLATFORM_NO_CAPABLE_CONNECTOR = "E5002"
    PLATFORM_CONFIG_INVALID = "E5003"
    PLATFORM_WORKFLOW_ERROR = "E5004"
    PLATFORM_INTERNAL = "E5005"


class ConnectorError(Exception):
    """Rich exception carrying an ErrorCode, severity, and remediation hint."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.PERMANENT,
        remediation: str = "",
        details: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.severity = severity
        self.remediation = remediation
        self.details = details or {}
        super().__init__(message)

    @property
    def retryable(self) -> bool:
        return self.severity == ErrorSeverity.TRANSIENT


# ---------------------------------------------------------------------------
# Error catalog — used by telemetry and developer docs to enumerate all
# known failure modes.
# ---------------------------------------------------------------------------

_CatalogEntry = tuple[ErrorCode, ErrorSeverity, str, str]

error_catalog: list[_CatalogEntry] = [
    # (code, severity, description, default_remediation)

    # Auth
    (ErrorCode.AUTH_INVALID_CREDENTIALS, ErrorSeverity.PERMANENT,
     "Credentials rejected by the target site.",
     "Re-enter credentials in the Connections page."),
    (ErrorCode.AUTH_SESSION_EXPIRED, ErrorSeverity.TRANSIENT,
     "Saved session is no longer valid.",
     "Platform will attempt re-authentication automatically."),
    (ErrorCode.AUTH_CAPTCHA_REQUIRED, ErrorSeverity.USER_ACTION,
     "Login page presented a CAPTCHA challenge.",
     "Complete manual browser login to create a fresh session."),
    (ErrorCode.AUTH_2FA_REQUIRED, ErrorSeverity.USER_ACTION,
     "Two-factor authentication prompt encountered.",
     "Complete 2FA manually in the browser login flow."),
    (ErrorCode.AUTH_ACCOUNT_LOCKED, ErrorSeverity.PERMANENT,
     "Account is locked or disabled on the target site.",
     "Contact the data provider to unlock the account."),
    (ErrorCode.AUTH_OAUTH_REFRESH_FAILED, ErrorSeverity.TRANSIENT,
     "OAuth token refresh failed.",
     "Re-authorize the connection in the Connections page."),
    (ErrorCode.AUTH_MISSING_CREDENTIALS, ErrorSeverity.PERMANENT,
     "No credentials configured for this connector.",
     "Add credentials in the Connections page."),

    # Network
    (ErrorCode.NET_TIMEOUT, ErrorSeverity.TRANSIENT,
     "Request timed out.", "Will retry with backoff."),
    (ErrorCode.NET_CONNECTION_REFUSED, ErrorSeverity.TRANSIENT,
     "Could not connect to the target site.", "Will retry with backoff."),
    (ErrorCode.NET_DNS_FAILURE, ErrorSeverity.TRANSIENT,
     "DNS resolution failed.", "Check network and retry."),
    (ErrorCode.NET_RATE_LIMITED, ErrorSeverity.TRANSIENT,
     "Rate limit exceeded on the target site.",
     "Will retry after cooldown."),
    (ErrorCode.NET_SERVER_ERROR, ErrorSeverity.TRANSIENT,
     "Target site returned a 5xx error.", "Will retry with backoff."),

    # Extraction
    (ErrorCode.EXTRACT_LAYOUT_CHANGED, ErrorSeverity.PERMANENT,
     "Expected page layout did not match; selectors may be stale.",
     "Report to connector maintainer for selector update."),
    (ErrorCode.EXTRACT_NO_DATA, ErrorSeverity.PERMANENT,
     "No data found for the given parameters.",
     "Verify the input parameters (address, date range, etc.)."),
    (ErrorCode.EXTRACT_PARSE_FAILURE, ErrorSeverity.PERMANENT,
     "Could not parse raw response into expected schema.",
     "Report to connector maintainer."),
    (ErrorCode.EXTRACT_SCHEMA_MISMATCH, ErrorSeverity.PERMANENT,
     "Normalized data does not match declared output schema.",
     "Report to connector maintainer."),

    # Security
    (ErrorCode.SEC_DOMAIN_BLOCKED, ErrorSeverity.PERMANENT,
     "Navigation attempted to a domain not on the allowlist.",
     "Update the connector manifest's allowed_domains."),
    (ErrorCode.SEC_RUNTIME_EXCEEDED, ErrorSeverity.PERMANENT,
     "Execution exceeded the maximum allowed runtime.",
     "Narrow the query or increase the runtime limit."),
    (ErrorCode.SEC_NAV_LIMIT_EXCEEDED, ErrorSeverity.PERMANENT,
     "Too many navigation steps executed.",
     "Simplify the workflow or increase nav step limit."),
    (ErrorCode.SEC_CONTENT_LIMIT_EXCEEDED, ErrorSeverity.PERMANENT,
     "Extracted content exceeded the size limit.",
     "Narrow the query scope."),
    (ErrorCode.SEC_BOT_DETECTED, ErrorSeverity.USER_ACTION,
     "The target site detected automated access.",
     "Complete a manual browser login to refresh the session."),

    # Platform
    (ErrorCode.PLATFORM_CONNECTOR_NOT_FOUND, ErrorSeverity.PERMANENT,
     "No connector registered with the given ID.",
     "Check connector_id spelling or register the connector."),
    (ErrorCode.PLATFORM_NO_CAPABLE_CONNECTOR, ErrorSeverity.PERMANENT,
     "No connector can fulfil the requested capability.",
     "Register a connector with the required capability."),
    (ErrorCode.PLATFORM_CONFIG_INVALID, ErrorSeverity.PERMANENT,
     "Connector configuration is invalid.",
     "Fix the manifest or connector config and reload."),
    (ErrorCode.PLATFORM_WORKFLOW_ERROR, ErrorSeverity.PERMANENT,
     "Workflow step execution failed unexpectedly.",
     "Check workflow definition and debug artifacts."),
    (ErrorCode.PLATFORM_INTERNAL, ErrorSeverity.PERMANENT,
     "An internal platform error occurred.",
     "Check platform logs with the trace_id."),
]
