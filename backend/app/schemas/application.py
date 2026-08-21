"""Pydantic schemas for application endpoints (E18; E21; Journey J11; J14).

This module serves the E18 ``/applications`` endpoints (student-facing
``CreateApplicationRequest`` and ``ApplicationResponse``) plus the E21
counselor dashboard response shape ``ApplicationWithStudentResponse`` which
extends the response with denormalised student fields. The E21 shape joins
the application to its student so the dashboard can render name/email/phone
without a second round trip.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import ApplicationStage as ApplicationStageEnum
from app.rbac.roles import Role


class CreateApplicationRequest(BaseModel):
    """Payload for ``POST /applications`` (E18; Journey J11)."""

    university_id: int = Field(ge=1)
    program_id: int = Field(ge=1)


class ApplicationResponse(BaseModel):
    """Application data returned by the E18 and E21 endpoints (J11; J14).

    The field set is the union of what E18 returns to the student and what
    E21 returns to the counselor; clients that only care about E18 fields
    (e.g. ``university_id``) can ignore the rest. ``stage`` uses the E25
    :class:`PipelineStage` enum values.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    branch_id: int | None
    student_id: int
    assigned_counselor_id: int | None
    university_id: int
    program_id: int
    stage: ApplicationStageEnum
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
