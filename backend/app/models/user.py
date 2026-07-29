from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


def normalize_email(email: str) -> str:
    """Canonicalize an email for storage and lookup (trim + lowercase).

    Signup and login must apply this identically or a differing casing
    silently fails to match the stored record.
    """
    return email.strip().lower()


class UserBase(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None

    @field_validator("email", mode="after")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return normalize_email(v)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    id: UUID
    email_verified: bool
    avatar_url: str | None
    is_active: bool
    is_admin: bool = False
    created_at: datetime
    has_completed_onboarding: bool = False

    model_config = {"from_attributes": True}


class UserInDB(UserResponse):
    password_hash: str | None

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="after")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return normalize_email(v)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return normalize_email(v)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class GoogleAuthCallback(BaseModel):
    code: str
    state: str | None = None
