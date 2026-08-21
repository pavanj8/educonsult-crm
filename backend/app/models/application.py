"""Application model (E18; E21; Requirements §5).

The E21 queue fields are nullable for backwards compatibility with rows
created by E18, which pre-dates the branch and counselor-assignment
columns. Follow-ups tracked for the tightening of these columns to NOT NULL:

- **E19 — Counselor Auto-Assignment** (Journey J12): populates
  ``assigned_counselor_id`` automatically on new applications.
- **E20 — Manual Counselor Reassignment** (Journey J13): allows manual
  updates of ``assigned_counselor_id`` (and ``branch_id``) via the staff
  reassignment API.
- **E21 — Counselor Dashboard & Queue** (this issue; Journey J14): the
  ``GET /applications/assigned-to-me`` endpoint reads
  ``branch_id`` / ``assigned_counselor_id`` for the role-scoped queue.

Until those follow-ups land, an ``Application`` may be persisted with
``branch_id IS NULL`` and/or ``assigned_counselor_id IS NULL``. The
constraints can be tightened in the respective follow-up issues when the
columns are reliably populated for new rows.
"""

from sqlalchemy import Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage as ApplicationStage

__all__ = ["Application", "ApplicationStage"]


class Application(TenantScopedBase):
    """Student application to a university/program (E18; E21)."""

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
