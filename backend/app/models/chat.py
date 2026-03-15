from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid4())


class AgentType(str, Enum):
    ORCHESTRATOR = "orchestrator"
    DEMOGRAPHICS = "demographics"
    TENANT_ROSTER = "tenant-roster"
    FOOT_TRAFFIC = "foot-traffic"
    VOID_ANALYSIS = "void-analysis"
    NOTIFICATION = "notification"
    # Data source agents
    PLACER = "placer"  # Placer.ai for visitor traffic and customer profiles
    SITEUSA = "siteusa"  # SiteUSA for vehicle traffic (VPD) and demographics
    COSTAR = "costar"  # CoStar for premium tenant/lease data
    OUTREACH = "outreach"  # Email blast agent


class MessageRole(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class WorkflowStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class Message(BaseModel):
    id: str = Field(default_factory=uuid_str)
    role: MessageRole
    content: str
    agent_type: Optional[AgentType] = None
    timestamp: datetime = Field(default_factory=utc_now)
    is_streaming: bool = False
    visible: bool = True


class WorkflowStep(BaseModel):
    id: str = Field(default_factory=uuid_str)
    agent_type: AgentType
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    description: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    message: Message
    workflow_steps: list[WorkflowStep] = []


class WebSocketMessage(BaseModel):
    type: str  # "message", "workflow_update", "agent_status", "error"
    data: dict
