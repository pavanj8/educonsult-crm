"""Application model (E18, E21; Requirements §5 Student Journey)."""


from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

# String-based enum matching the pattern used in app.rbac.roles.Role
_application_stage_values = [
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
]

ApplicationStage = type(
    "ApplicationStage",
    (str,),
    {name.upper(): name for name in _application_stage_values},
)


APPLICATION_STAGE_ENUM = Enum(
    name="application_stage",
    **{v: v for v in _application_stage_values},
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
