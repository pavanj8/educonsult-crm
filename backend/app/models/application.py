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
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase


class PipelineStage(StrEnum):
    """Application pipeline stages (Requirements §5, Journey J18).

    Mirrors the canonical enum in :mod:`app.pipeline.stages`; we re-export a
    copy here so this module can be imported without pulling in the heavier
    pipeline package (which depends on the seeder). Values must stay in sync.
    """

    REGISTERED = "registered"
    COUNSELING = "counseling"
    UNIVERSITY_SHORTLISTING = "university_shortlisting"
    APPLICATION_SUBMITTED = "application_submitted"
    DOCUMENT_VERIFICATION = "document_verification"
    OFFER_LETTER = "offer_letter"
    VISA_PROCESSING = "visa_processing"
    LOAN_PROCESSING = "loan_processing"
    ENROLLED = "enrolled"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


# Terminal states - applications cannot progress further from these
_TERMINAL_STAGES = frozenset(
    {
        PipelineStage.ENROLLED,
        PipelineStage.REJECTED,
        PipelineStage.WITHDRAWN,
    }
)


def is_terminal_stage(stage: PipelineStage) -> bool:
    """Return True if the stage is a terminal state."""
    return stage in _TERMINAL_STAGES


class Application(TenantScopedBase):
    """Student application for a university/program (E18/E21; J11/J14).

    Each student can have multiple applications in parallel, each with its
    own independent pipeline stage. The set of columns is the union of what
    E18 (``/applications`` endpoints, Issue #149) and E21
    (``/counselor/queue`` endpoints, Issue #156) need to read/write.
    """

    __tablename__ = "applications"

    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # E18 — explicit university/program identifiers the application is for.
    # Required for student-created applications (E18 ``POST /applications``);
    # the E21 counselor queue tests seed ``None`` and bypass the router, so
    # both code paths share the same model.
    university_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    program_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # E21 — counselor that owns this application in the queue (nullable
    # while an application is freshly registered and round-robin has not yet
    # assigned a counselor; see E19).
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
    # Pipeline stage — stored as plain text so we can transition without a
    # Postgres ENUM migration; values are constrained at the application
    # layer (see E25 / :mod:`app.pipeline.default_transitions`).
    stage: Mapped[PipelineStage] = mapped_column(
        String(50),
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
    # Loan tracking fields (Requirements §5, Journey J29/J30)
    loan_opted_in: Mapped[bool] = mapped_column(Integer, nullable=False, default=False)
    loan_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    loan_lender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    loan_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)