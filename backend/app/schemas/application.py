"""Application schemas (E18, E21)."""

from pydantic import BaseModel, ConfigDict


class ApplicationQueueItem(BaseModel):
    """A single item in the counselor's application queue (GET /counseling/queue)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_name: str
    stage: str
    branch_id: int
    assigned_counselor_id: int | None = None
