"""Meeting model for counselor-scheduled student meetings (E22; J15).

Every meeting is tenant-scoped and belongs to one application, counselor,
and student. Foreign keys cascade when the associated record is deleted.
The ``application_id`` and ``student_id`` columns are indexed because
they are exposed as query parameters on the E22 ``GET /meetings`` list
endpoint (J15) and the E23 ``GET /meetings/upcoming`` student feed (J16).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase


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
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
