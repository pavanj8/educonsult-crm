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
    created_at: datetime
    updated_at: datetime
