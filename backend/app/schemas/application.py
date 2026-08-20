"""Pydantic schemas for application endpoints (E18/E21; Journey J11/J14)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.application import PipelineStage
from app.rbac.roles import Role


class ApplicationResponse(BaseModel):
    """Response schema for a single application."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    student_id: int
    assigned_counselor_id: int | None
    target_university_id: int | None
    target_program_id: int | None
    stage: PipelineStage
    stage_reason: str | None
    enrollment_date: datetime | None
    loan_opted_in: bool
    loan_status: str | None
    loan_lender: str | None
    loan_amount: int | None
    created_at: datetime
    updated_at: datetime


class ApplicationWithStudentResponse(ApplicationResponse):
    """Application response with student details included."""

    model_config = ConfigDict(from_attributes=True)

    # Student fields for display
    student_name: str | None
    student_email: str
    student_phone: str | None
    student_role: Role
