<<<<<<< HEAD
"""Meeting model for counselor scheduling (E22; Journey J15)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
=======
"""Meeting model for counselor-scheduled student meetings (E22; J15)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
>>>>>>> origin/main
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

<<<<<<< HEAD

class Meeting(TenantScopedBase):
    """A counselor meeting associated with a student application."""

    __tablename__ = "meetings"
    __table_args__ = (
        Index(
            "ix_meetings_tenant_counselor_scheduled",
            "tenant_id",
            "counselor_id",
            "scheduled_at",
        ),
    )

    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    counselor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
=======
__all__ = ["Meeting"]


class Meeting(TenantScopedBase):
    """A meeting between a counselor and a student for an application."""

    __tablename__ = "meetings"

    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counselor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
>>>>>>> origin/main
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
