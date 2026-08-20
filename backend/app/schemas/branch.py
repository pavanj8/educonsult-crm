"""Pydantic schemas for branch management endpoints (E11; Journey J4)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BranchCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)

    @field_validator("name", "city")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty")
        return stripped


class BranchUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("name", "city")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty")
        return stripped


class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    city: str
    created_at: datetime
    updated_at: datetime
