"""Pydantic schemas for staff management endpoints (E12; Journey J5)."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.rbac.roles import Role

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class StaffCreateRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)
    role: Role
    branch_id: int = Field(ge=1)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Email must not be empty")
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError("Email must be a valid email address")
        return normalized


class StaffUpdateRequest(BaseModel):
    role: Role | None = None
    branch_id: int | None = Field(default=None, ge=1)


class StaffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role
    tenant_id: int
    branch_id: int
    created_at: datetime
    updated_at: datetime
