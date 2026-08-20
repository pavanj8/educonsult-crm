"""Pydantic schemas for tenant management endpoints (E8; Journey J1)."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100)
    owner_email: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name must not be empty")
        return stripped

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Slug must not be empty")
        if not _SLUG_PATTERN.match(normalized):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )
        return normalized

    @field_validator("owner_email")
    @classmethod
    def normalize_owner_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Owner email must not be empty")
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError("Owner email must be a valid email address")
        return normalized


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime
