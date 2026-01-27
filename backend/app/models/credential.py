from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SiteCredentialBase(BaseModel):
    site_name: str
    site_url: str
    username: str


class SiteCredentialCreate(SiteCredentialBase):
    password: str
    additional_config: dict | None = None


class SiteCredentialUpdate(BaseModel):
    site_url: str | None = None
    username: str | None = None
    password: str | None = None
    additional_config: dict | None = None


class SiteCredentialResponse(BaseModel):
    id: UUID
    site_name: str
    site_url: str
    username: str
    is_verified: bool
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Session tracking
    session_status: str = "unknown"
    session_last_checked: datetime | None = None
    session_error_message: str | None = None
    # Usage tracking
    last_used_at: datetime | None = None
    total_uses: int = 0
    # CAPTCHA/manual login info
    requires_manual_login: bool = False

    model_config = {"from_attributes": True}


class ConnectorStatusResponse(BaseModel):
    """Health status for a single connector (returned by GET /connectors/status)."""
    credential_id: UUID
    site_name: str
    site_display_name: str
    connector_status: str  # connected | stale | needs_reauth | degraded | error | disabled
    last_probe_at: datetime | None
    last_used_at: datetime | None
    session_error_message: str | None
    requires_manual_login: bool = False

    model_config = {"from_attributes": True}


class ConnectorProbeResponse(BaseModel):
    """Result of an on-demand health probe."""
    credential_id: UUID
    connector_status: str
    probe_duration_ms: int
    message: str


class AgentConnectionResponse(BaseModel):
    id: UUID
    agent_type: str
    status: str
    last_connected_at: datetime | None
    error_message: str | None
    credential_id: UUID | None

    model_config = {"from_attributes": True}


class VerifyCredentialResponse(BaseModel):
    success: bool
    message: str
    # CAPTCHA-specific fields
    captcha_detected: bool = False
    captcha_type: str | None = None
    requires_manual_session: bool = False
    error_type: str | None = None
    screenshot_path: str | None = None
