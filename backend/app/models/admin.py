from datetime import datetime

from pydantic import BaseModel


# --- Overview ---

class SignupBucket(BaseModel):
    date: str
    count: int


class AdminOverview(BaseModel):
    total_users: int
    active_users_30d: int
    new_users_7d: int
    new_users_30d: int
    total_sessions: int
    total_documents: int
    total_deals: int
    total_projects: int
    signups_over_time: list[SignupBucket]


# --- Users ---

class AdminUserSummary(BaseModel):
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    tier: str
    is_active: bool
    session_count: int
    document_count: int
    deal_count: int
    project_count: int
    created_at: datetime
    last_active: datetime | None


class AdminUserList(BaseModel):
    users: list[AdminUserSummary]
    total: int
    page: int
    page_size: int


# --- User Detail ---

class TokenUsageSummary(BaseModel):
    period_start: datetime
    input_tokens: int
    output_tokens: int
    llm_calls: int


class RecentSession(BaseModel):
    id: str
    title: str | None
    message_count: int
    created_at: datetime


class AdminUserDetail(BaseModel):
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    tier: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    session_count: int
    document_count: int
    deal_count: int
    project_count: int
    token_usage: list[TokenUsageSummary]
    recent_sessions: list[RecentSession]


# --- Usage ---

class TopConsumer(BaseModel):
    user_id: str
    email: str
    input_tokens: int
    output_tokens: int
    llm_calls: int
    total_tokens: int


class AdminUsage(BaseModel):
    period_label: str
    total_input_tokens: int
    total_output_tokens: int
    total_llm_calls: int
    top_consumers: list[TopConsumer]


# --- Abuse ---

class AbuseFlag(BaseModel):
    user_id: str
    email: str
    reason: str
    severity: str  # "low", "medium", "high"
    detail: str


class AdminAbuse(BaseModel):
    flags: list[AbuseFlag]
