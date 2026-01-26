"""
Agent Communication Protocols

Structured protocols for master-sub agent communication including:
- NeedMoreInfo: When a sub-agent needs additional input to proceed
- ToolFailure: When a tool execution fails
- AgentResult: Successful result with metadata
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime


class InfoRequirementType(str, Enum):
    """Types of information a sub-agent might need."""
    LOCATION_PRECISION = "location_precision_required"
    ADDRESS_REQUIRED = "address_required"
    ZIP_REQUIRED = "zip_required"
    CREDENTIALS_REQUIRED = "credentials_required"
    CLARIFICATION_NEEDED = "clarification_needed"
    DATE_RANGE_REQUIRED = "date_range_required"
    BUSINESS_TYPE_REQUIRED = "business_type_required"


class ToolErrorCode(str, Enum):
    """Standardized error codes for tool failures."""
    # Input errors
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_LOCATION = "invalid_location"

    # Authentication/Authorization
    AUTH_REQUIRED = "auth_required"
    AUTH_EXPIRED = "auth_expired"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"

    # External service errors
    SERVICE_UNAVAILABLE = "service_unavailable"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    API_ERROR = "api_error"

    # Data errors
    NO_DATA_FOUND = "no_data_found"
    PARTIAL_DATA = "partial_data"
    DATA_QUALITY_LOW = "data_quality_low"

    # Internal errors
    INTERNAL_ERROR = "internal_error"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass
class NeedMoreInfo:
    """
    Protocol for sub-agents to request additional information.

    The master agent handles this by:
    1. Trying to satisfy required_fields via resolve_location or other resolvers
    2. If still missing, asking the user a minimal question
    3. Retrying the sub-agent with enriched context
    """
    type: InfoRequirementType
    agent_name: str
    required_fields: list[str]
    optional_fields: list[str] = field(default_factory=list)
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    user_message: str | None = None  # Suggested message to show user

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": "need_more_info",
            "type": self.type.value,
            "agent_name": self.agent_name,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
            "suggestions": self.suggestions,
            "context": self.context,
            "user_message": self.user_message,
        }

    @classmethod
    def location_precision_required(
        cls,
        agent_name: str,
        current_input: str,
        suggestions: list[str] | None = None,
    ) -> "NeedMoreInfo":
        """Create a NeedMoreInfo for location precision requirements."""
        return cls(
            type=InfoRequirementType.LOCATION_PRECISION,
            agent_name=agent_name,
            required_fields=["zip_code", "address", "place_fips"],
            optional_fields=["state_fips", "county_fips"],
            suggestions=[{"value": s} for s in (suggestions or [])],
            context={"original_input": current_input},
            user_message=f"I need more specific location information for {current_input}. Could you provide a ZIP code or street address?",
        )


@dataclass
class ToolFailure:
    """
    Protocol for reporting tool execution failures.

    The master agent handles this by:
    1. Checking if retryable and attempting retry with backoff
    2. Using fallback_recommendation if available
    3. Reporting the failure to the user if unrecoverable
    """
    tool_name: str
    error_code: ToolErrorCode
    error_message: str
    retryable: bool = False
    retry_after_seconds: int | None = None
    fallback_recommendation: str | None = None
    partial_result: Any = None
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": "tool_failure",
            "tool_name": self.tool_name,
            "error_code": self.error_code.value,
            "error_message": self.error_message,
            "retryable": self.retryable,
            "retry_after_seconds": self.retry_after_seconds,
            "fallback_recommendation": self.fallback_recommendation,
            "partial_result": self.partial_result,
            "context": self.context,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    @classmethod
    def location_not_found(cls, tool_name: str, location: str) -> "ToolFailure":
        """Create a ToolFailure for location not found errors."""
        return cls(
            tool_name=tool_name,
            error_code=ToolErrorCode.INVALID_LOCATION,
            error_message=f"Could not find location: {location}",
            retryable=False,
            fallback_recommendation="Try providing a more specific address or ZIP code",
            context={"location": location},
        )

    @classmethod
    def auth_required(cls, tool_name: str, service_name: str) -> "ToolFailure":
        """Create a ToolFailure for authentication requirements."""
        return cls(
            tool_name=tool_name,
            error_code=ToolErrorCode.AUTH_REQUIRED,
            error_message=f"{service_name} credentials required",
            retryable=False,
            fallback_recommendation=f"Please add your {service_name} credentials in Settings > Connections",
            context={"service": service_name},
        )

    @classmethod
    def service_error(
        cls,
        tool_name: str,
        service_name: str,
        error: str,
        retryable: bool = True,
    ) -> "ToolFailure":
        """Create a ToolFailure for external service errors."""
        return cls(
            tool_name=tool_name,
            error_code=ToolErrorCode.SERVICE_UNAVAILABLE,
            error_message=f"{service_name} error: {error}",
            retryable=retryable,
            retry_after_seconds=5 if retryable else None,
            context={"service": service_name, "original_error": error},
        )


@dataclass
class AgentResult:
    """
    Successful result from an agent with metadata.
    """
    agent_name: str
    content: str
    data: dict[str, Any] | None = None
    confidence: float = 1.0  # 0.0 to 1.0
    sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    execution_time_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": "agent_result",
            "agent_name": self.agent_name,
            "content": self.content,
            "data": self.data,
            "confidence": self.confidence,
            "sources": self.sources,
            "warnings": self.warnings,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class InferredFallback:
    """
    When an agent uses inferred data or fallback logic.
    Should be disclosed to user for transparency.
    """
    agent_name: str
    original_request: str
    fallback_used: str
    reason: str
    confidence_impact: float  # How much confidence was reduced (0.0 to 1.0)
    disclosure_message: str  # Message to show user

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": "inferred_fallback",
            "agent_name": self.agent_name,
            "original_request": self.original_request,
            "fallback_used": self.fallback_used,
            "reason": self.reason,
            "confidence_impact": self.confidence_impact,
            "disclosure_message": self.disclosure_message,
        }


def format_tool_failure_for_user(failure: ToolFailure) -> str:
    """Format a tool failure as a user-friendly message."""
    message = f"**{failure.tool_name}** encountered an issue: {failure.error_message}"

    if failure.fallback_recommendation:
        message += f"\n\n*Suggestion:* {failure.fallback_recommendation}"

    if failure.partial_result:
        message += "\n\nPartial results were available and have been included."

    return message


def format_need_more_info_for_user(info: NeedMoreInfo) -> str:
    """Format a NeedMoreInfo request as a user-friendly message."""
    if info.user_message:
        return info.user_message

    fields = ", ".join(info.required_fields)
    return f"To provide accurate {info.agent_name} data, I need additional information: {fields}"
