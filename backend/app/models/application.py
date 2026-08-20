"""Application model (E18; E21; Requirements §5).

E21 · Journey J14: Counselor views their assigned student/application queue.
Adds ``branch_id`` (every application belongs to exactly one branch) and
``assigned_counselor_id`` (the counselor who owns the application, nullable
until auto-assignment runs in E19).

Both columns are added as nullable in this issue for the migration to be
back-compatible with rows already created by E18 / ``create_application``
(which does not yet capture them). Future epics (E19 — auto-assignment,
E20 — manual reassignment, E21 task for branch ownership on creation) will
populate these and the constraints can be tightened in their respective
issues.

The pipeline stage enum lives in :mod:`app.pipeline.stages` (the canonical
home, also imported by the stage-progression service and transition rules)
and is re-exported here as :class:`ApplicationStage` so ORM code and tests
have a model-natural name.
"""

from sqlalchemy import Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage as ApplicationStage

__all__ = ["Application", "ApplicationStage"]


class Application(TenantScopedBase):
    """Student application to a university/program (E18; E21; Requirements §5).

    Each student can have multiple applications in parallel, each with its own
    independent pipeline stage. Counselors are assigned to applications via
    ``assigned_counselor_id``; the application lives in a single ``branch_id``
    (E21 queue scoping).
    """

    __tablename__ = "applications"

    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_counselor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    university_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(
            ApplicationStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=ApplicationStage.REGISTERED,
    )
