<<<<<<< HEAD
"""Application model (E18/E21; Journey J11/J14).

The :class:`Application` table is the central record of a student's pursuit of
a specific university/program combination. Multiple applications per student
are allowed and each tracks its own pipeline stage independently.

Fields are kept as a superset of:
- E18 backend requirements (university_id/program_id; Issue #145/#146/#149)
- E21 counselor dashboard requirements (assigned_counselor_id, target_*,
  stage_reason, enrollment_date, loan tracking fields; Issue #156)
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
=======
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
>>>>>>> origin/main
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage as ApplicationStage

__all__ = ["Application", "ApplicationStage"]

__all__ = ["Application"]


class Application(TenantScopedBase):
<<<<<<< HEAD
    """Student application to a university/program (E18/E21; Journey J11/J14).

    Each student can have multiple applications in parallel, each with its
    own independent pipeline stage. ``university_id`` and ``program_id`` are
    required by E18 (``POST /applications``) and remain NOT NULL; the
    E21-specific fields are nullable where appropriate (counselor not yet
    assigned, loan not opted-in, etc.).
    """
=======
    """Student application to a university/program (E18; E21)."""
>>>>>>> origin/main

    __tablename__ = "applications"

    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
<<<<<<< HEAD
    # E18 — explicit university/program identifiers the application is for.
    university_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # E21 — counselor that owns this application in the queue (nullable
    # while an application is freshly registered and round-robin has not
    # yet assigned a counselor; see E19).
    assigned_counselor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # E21 — denormalized target university/program references kept alongside
    # the E18 fields above for the counselor queue filters. These were the
    # names originally chosen for the E21 endpoints and are preserved to
    # keep that contract stable.
    target_university_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    target_program_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Pipeline stage — stored as a non-native enum so we can transition
    # without a Postgres ENUM migration; values are constrained at the
    # application layer (see E25 / :mod:`app.pipeline.default_transitions`).
    stage: Mapped[PipelineStage] = mapped_column(
=======
    assigned_counselor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    university_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    stage: Mapped[ApplicationStage] = mapped_column(
>>>>>>> origin/main
        Enum(
            ApplicationStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
<<<<<<< HEAD
        default=PipelineStage.REGISTERED,
        index=True,
=======
        default=ApplicationStage.REGISTERED,
>>>>>>> origin/main
    )
    # Optional reason for terminal stages (rejected/withdrawn)
    stage_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Enrollment details
    enrollment_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Loan tracking fields (Requirements §5, Journey J29/J30).
    # Use ``Boolean`` so ORM reads return real ``bool`` values; the Pydantic
    # schema can rely on the typed value rather than coercing ints.
    loan_opted_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    loan_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    loan_lender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    loan_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
