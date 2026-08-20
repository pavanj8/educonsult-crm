"""Pydantic schemas for application endpoints (E18; E21; Journey J11; J14).

``ApplicationStageEnum`` is a re-export of :class:`app.models.application.ApplicationStage`
so Pydantic, ORM, and FastAPI route handlers share one enum definition
(avoids duplication / drift).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import ApplicationStage as ApplicationStageEnum


class CreateApplicationRequest(BaseModel):
    university_id: int = Field(ge=1)
    program_id: int = Field(ge=1)


class ApplicationResponse(BaseModel):
    """Single application record in list/detail responses (E18; E21).

    Field notes:
    - ``tenant_id`` is included so existing E18 list/detail callers that echo
      it back keep working (tenant scoping is already enforced by the route;
      echoing the value is a convenience for clients).
    - ``branch_id`` and ``assigned_counselor_id`` are nullable. They are
      back-filled by the E19 (auto-assignment) and E20 (manual reassignment)
      tasks; rows created by E18 ``POST /applications`` do not yet carry a
      branch, and they remain ``NULL`` until those epics land. The schema
      matches the ORM (where both columns are ``nullable=True``) so existing
      rows do not raise 500s.
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
