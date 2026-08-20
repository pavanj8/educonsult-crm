from enum import StrEnum

from sqlalchemy import Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase


class ApplicationStage(StrEnum):
    """Pipeline stage for a student application (Requirements §5, ADR-0005)."""

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
    """Student university/program application (E18; Requirements §5).

    Each row represents one application with its own independent pipeline stage.
    ``student_id`` references ``users.id`` where ``role=STUDENT``.
    ``university_id`` and ``program_id`` reference master data tables (E14).
    """

    __tablename__ = "applications"

    student_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
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
