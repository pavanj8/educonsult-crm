"""Application model (E18, E21; Requirements §5 Student Journey)."""

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

# All valid pipeline stage values — single source of truth used both by the
# SQLAlchemy enum column and by the counseling queue's input validator.
APPLICATION_STAGES = (
    "registered",
    "counseling",
    "university_shortlisting",
    "application_submitted",
    "document_verification",
    "offer_letter",
    "visa_processing",
    "loan_processing",
    "enrolled",
    "rejected",
    "withdrawn",
)

# Frozenset derived from the tuple so O(1) lookup is available to callers
# (e.g. the counseling router's input validator) without re-declaring the list.
VALID_APPLICATION_STAGES = frozenset(APPLICATION_STAGES)

APPLICATION_STAGE_ENUM = Enum(
    *APPLICATION_STAGES,
    name="application_stage",
    native_enum=True,
    create_constraint=False,
)


class Application(TenantScopedBase):
    """A student's application to a university/program (E18; Requirements §5).

    A student can have multiple parallel applications. Each has an independent
    pipeline stage. Counselors are assigned per-application.
    """

    __tablename__ = "applications"

    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    university_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    program_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_counselor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    branch_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    stage: Mapped[str] = mapped_column(
        APPLICATION_STAGE_ENUM,
        nullable=False,
        default="registered",
    )
    student_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
