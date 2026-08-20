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
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage

__all__ = ["Application"]


class Application(TenantScopedBase):
    """Student application to a university/program (E18/E21; Journey J11/J14).

    Each student can have multiple applications in parallel, each with its
    own independent pipeline stage. ``university_id`` and ``program_id`` are
    required by E18 (``POST /applications``) and remain NOT NULL; the
    E21-specific fields are nullable where appropriate (counselor not yet
    assigned, loan not opted-in, etc.).
    """

    __tablename__ = "applications"

    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
        Enum(
            PipelineStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=PipelineStage.REGISTERED,
        index=True,
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
