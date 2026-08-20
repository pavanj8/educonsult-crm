<<<<<<< HEAD
"""Application model (E18/E21; Journey J11/J14)."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase


class PipelineStage(StrEnum):
    """Application pipeline stages (Requirements §5, Journey J18)."""

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
    """Student application for a university/program (E18; Requirements §5).

    Each student can have multiple applications in parallel, each with its own
    independent pipeline stage.
=======
from sqlalchemy import Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage


class Application(TenantScopedBase):
    """Student university/program application (E18; Journey J11).

    ``university_id`` and ``program_id`` reference master data tables added in E14.
>>>>>>> origin/main
    """

    __tablename__ = "applications"

    student_id: Mapped[int] = mapped_column(
        Integer,
<<<<<<< HEAD
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Assigned counselor for this application
    assigned_counselor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Target university and program
    target_university_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    target_program_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Pipeline stage
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
=======
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    university_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    stage: Mapped[PipelineStage] = mapped_column(
        Enum(
            PipelineStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=PipelineStage.REGISTERED,
    )
>>>>>>> origin/main
