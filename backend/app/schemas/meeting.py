"""Meeting API schemas (E22; Journey J15)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MeetingCreate(BaseModel):
    application_id: int = Field(gt=0)
    student_id: int = Field(gt=0)
    counselor_id: int = Field(gt=0)
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class MeetingUpdate(BaseModel):
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    application_id: int
    student_id: int
    counselor_id: int
    scheduled_at: datetime
    duration_minutes: int
    location: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
