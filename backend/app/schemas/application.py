"""Application schemas (E18, E21)."""

from pydantic import BaseModel, ConfigDict


class ApplicationQueueItem(BaseModel):
    """A single item in the counselor's application queue (GET /counseling/queue).

    Attributes:
        id: Unique application identifier.
        student_id: ID of the student who owns the application (for deep-linking).
        student_name: Full name of the student.
        stage: Current pipeline stage of the application.
        branch_id: Branch the application belongs to (included for debugging;
            callers scoped to a single counselor/branch may not need it).
        assigned_counselor_id: ID of the counselor assigned to this application
            (included for debugging; the queue is already filtered to the
            caller's own applications).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    student_name: str
    stage: str
    branch_id: int
    assigned_counselor_id: int | None = None
