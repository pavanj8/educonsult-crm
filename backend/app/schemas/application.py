<<<<<<< HEAD
"""Pydantic schemas for application endpoints (E18/E21; Journey J11/J14).

This module serves the E18 ``/applications`` endpoints (student-facing
``CreateApplicationRequest`` and ``ApplicationResponse``) plus the E21
counselor dashboard response shape ``ApplicationWithStudentResponse``
which extends the response with denormalised student fields.
"""
=======
"""Pydantic schemas for application endpoints (E18; E21; Journey J11; J14)."""
>>>>>>> origin/main

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

<<<<<<< HEAD
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
=======
from app.models.application import ApplicationStage as ApplicationStageEnum
>>>>>>> origin/main


class CreateApplicationRequest(BaseModel):
    """Payload for ``POST /applications`` (E18; Journey J11)."""

    university_id: int = Field(ge=1)
    program_id: int = Field(ge=1)


class ApplicationResponse(BaseModel):
<<<<<<< HEAD
    """Response schema for a single application.

    The field set is the union of what E18 returns to the student and what
    E21 returns to the counselor; clients that only care about E18 fields
    (e.g. ``university_id``) can ignore the rest.
    """
=======
    """Application data returned by the E18 and E21 endpoints."""
>>>>>>> origin/main

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    branch_id: int | None
    student_id: int
<<<<<<< HEAD
    # E18 fields (NOT NULL; required by POST /applications)
    university_id: int
    program_id: int
    # E21 fields (nullable where the lifecycle has not yet reached them)
    assigned_counselor_id: int | None
    target_university_id: int | None
    target_program_id: int | None
    # Pipeline stage + resolution metadata
    stage: PipelineStage
    stage_reason: str | None
    enrollment_date: datetime | None
    # Loan tracking
    loan_opted_in: bool
    loan_status: str | None
    loan_lender: str | None
    loan_amount: int | None
    # Bookkeeping
=======
    assigned_counselor_id: int | None
    university_id: int
    program_id: int
    stage: ApplicationStageEnum
>>>>>>> origin/main
    created_at: datetime
    updated_at: datetime


class ApplicationWithStudentResponse(ApplicationResponse):
    """Application response with student details included (E21; Journey J14).

    The counselor queue endpoint joins the application to its student and
    returns this richer shape so the dashboard can render name/email/phone
    directly without a second round trip.
    """

    model_config = ConfigDict(from_attributes=True)

    student_name: str | None
    student_email: str
    student_phone: str | None
    student_role: Role
