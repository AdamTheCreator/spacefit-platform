"""
Connector manifest schema.

Each connector declares its identity, auth requirements, execution modes,
capabilities, rate limits, required inputs, and output shape via a manifest.
Manifests are loaded from YAML or JSON files by the ConnectorRegistry.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AuthType(str, Enum):
    OAUTH = "oauth"
    API_KEY = "api_key"
    USERNAME_PASSWORD = "username_password"
    SESSION_STATE = "session_state"


class ExecutionMode(str, Enum):
    API = "api"
    HYBRID = "hybrid"
    BROWSER = "browser"


class RateLimitPolicy(BaseModel):
    requests_per_minute: int = Field(default=60, ge=1)
    burst: int = Field(default=10, ge=1)
    cooldown_seconds: int = Field(default=1, ge=0)


class SecretField(BaseModel):
    key: str
    description: str = ""
    required: bool = True


class UserInput(BaseModel):
    key: str
    label: str
    type: str = "string"  # string, url, email, select
    required: bool = True
    description: str = ""
    options: list[str] | None = None  # For select type


class OutputSchemaRef(BaseModel):
    """Reference to a JSON Schema for the connector's normalized output."""
    ref: str = ""  # File path or inline
    inline: dict[str, Any] | None = None


class RuntimeLimits(BaseModel):
    max_runtime_seconds: int = Field(default=120, ge=1)
    max_navigation_steps: int = Field(default=50, ge=1)
    max_extracted_bytes: int = Field(default=10_000_000, ge=1)  # 10 MB


class ConnectorManifest(BaseModel):
    """
    Full connector declaration. Loaded from YAML/JSON at startup.
    """

    connector_id: str = Field(
        ..., description="Unique slug, e.g. 'google_places'"
    )
    name: str = Field(..., description="Human-readable name")
    version: str = Field(default="1.0.0")
    description: str = ""

    # Auth
    auth_type: AuthType
    auth_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Auth-type-specific config (e.g. oauth endpoints, scopes)",
    )

    # Execution
    execution_modes: list[ExecutionMode] = Field(
        ..., min_length=1, description="Supported execution modes, ordered by preference"
    )
    default_mode: ExecutionMode | None = None

    # Security
    allowed_domains: list[str] = Field(
        ..., min_length=1, description="Strict domain allowlist"
    )

    # Capabilities
    capabilities: list[str] = Field(
        ..., min_length=1, description="Tags describing what data this connector fetches"
    )

    # Rate limits
    rate_limit: RateLimitPolicy = Field(default_factory=RateLimitPolicy)

    # Runtime limits
    runtime_limits: RuntimeLimits = Field(default_factory=RuntimeLimits)

    # User inputs and secrets
    required_inputs: list[UserInput] = Field(default_factory=list)
    required_secrets: list[SecretField] = Field(default_factory=list)

    # Output
    output_schema: OutputSchemaRef = Field(default_factory=OutputSchemaRef)

    # Workflow reference (for data-driven execution)
    workflow_file: str | None = Field(
        default=None,
        description="Path to workflow YAML relative to manifest directory",
    )

    # Connector implementation module
    module: str = Field(
        ...,
        description="Python dotted path to connector class, e.g. 'app.connectors.examples.google_places.connector.GooglePlacesConnector'",
    )

    # Metadata
    maintainer: str = ""
    tags: list[str] = Field(default_factory=list)

    @property
    def preferred_mode(self) -> ExecutionMode:
        return self.default_mode or self.execution_modes[0]
