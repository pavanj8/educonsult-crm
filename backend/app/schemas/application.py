"""Pydantic schemas for application endpoints (E18; Journey J11)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.pipeline.stages import PipelineStage


class CreateApplicationRequest(BaseModel):
    university_id: int = Field(ge=1)
    program_id: int = Field(ge=1)


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    student_id: int
    university_id: int
    program_id: int
    stage: PipelineStage
    created_at: datetime
    updated_at: datetime
