"""Pydantic schemas for authentication endpoints (E5)."""

from pydantic import BaseModel, Field

from app.rbac.roles import Role


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    id: int
    email: str
    role: Role
    tenant_id: int | None
    branch_id: int | None
