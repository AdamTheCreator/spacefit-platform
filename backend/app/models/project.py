"""
Pydantic models for the Projects API.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.deal import PropertyResponse
from app.models.document import ParsedDocumentResponse


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    property_id: str | None = None
    description: str | None = None
    instructions: str | None = None
    property_address: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    property_id: str | None = None
    description: str | None = None
    instructions: str | None = None
    property_address: str | None = None


class ChatSessionBrief(BaseModel):
    id: UUID
    title: str | None = None
    analysis_type: str | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    property_id: UUID | None = None
    name: str
    description: str | None = None
    instructions: str | None = None
    property_address: str | None = None
    is_archived: bool = False
    document_count: int = 0
    session_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    property: PropertyResponse | None = None
    documents: list[ParsedDocumentResponse] = []
    sessions: list[ChatSessionBrief] = []


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
