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

    model_config = {"from_attributes": True}


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
