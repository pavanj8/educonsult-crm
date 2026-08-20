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

    ``tenant_id`` is intentionally omitted: every response served by the API
    is already tenant-scoped via the caller's session, so echoing the value
    back provides no extra information and widens the surface for accidental
    client misuse.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    student_id: int
    assigned_counselor_id: int | None
    university_id: int
    program_id: int
    stage: ApplicationStageEnum
    created_at: datetime
    updated_at: datetime
