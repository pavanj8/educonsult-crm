<<<<<<< HEAD
"""Pydantic schemas for application endpoints (E21; Journey J14).

``ApplicationStageEnum`` is re-exported from the model so both ORM and schema
layers share a single enum definition (avoids duplication / drift).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

# Re-export so FastAPI route handlers and schema consumers import from one place.
from app.models.application import ApplicationStage as ApplicationStageEnum


class ApplicationResponse(BaseModel):
    """Single application record in list/detail responses (E21)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    student_id: int
    assigned_counselor_id: int | None
    university: str
    program: str
    stage: ApplicationStageEnum
=======
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
>>>>>>> origin/main
    created_at: datetime
    updated_at: datetime
