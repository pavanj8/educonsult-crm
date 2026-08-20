<<<<<<< HEAD
"""Application model and pipeline stage enum (E18; Requirements §5).

E38 · Journey J31: Mark Enrolled  — adds ``enrolled_at`` column
E39 · Journey J32: Mark Rejected   — adds ``rejection_reason`` column
E40 · Journey J33: Mark Withdrawn  — adds ``withdrawal_reason`` column
"""

from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase


class ApplicationStage(StrEnum):
    """Per-application pipeline stages (Requirements §5).

    Terminal states: ENROLLED, REJECTED, WITHDRAWN.
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


class Application(TenantScopedBase):
    """Student application to a university/program (E18; Requirements §5).

    Each student can have multiple applications in parallel, each with its own
    independent pipeline stage. Counselors are assigned to applications via
    ``assigned_counselor_id``.
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

<<<<<<< HEAD
    branch_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
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
    university: Mapped[str] = mapped_column(String(255), nullable=False)
    program: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(
            ApplicationStage,
=======
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    university_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    stage: Mapped[PipelineStage] = mapped_column(
        Enum(
            PipelineStage,
>>>>>>> origin/main
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
<<<<<<< HEAD
        default=ApplicationStage.REGISTERED,
=======
        default=PipelineStage.REGISTERED,
>>>>>>> origin/main
    )
