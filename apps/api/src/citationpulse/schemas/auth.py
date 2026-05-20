from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self) -> SignupRequest:
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    remember: bool = False


class AdminLoginRequest(BaseModel):
    """Username (display name) or email — e.g. Traffic-Radius."""
    username: str = Field(..., min_length=1, max_length=320)
    password: str = Field(..., min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    tenant_id: UUID | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserPublic


class MessageResponse(BaseModel):
    message: str
