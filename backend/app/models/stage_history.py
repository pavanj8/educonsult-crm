"""StageHistory model (E25; Journey J18).

Append-only audit log of every stage transition an application goes
through. Written by the ``POST /applications/{id}/stage`` endpoint
(advance-stage API, issue #169) and consumed by the E25 frontend stage
timeline component (and any future analytics / audit views).

Each row records:

* which application moved (``application_id``),
* what stage it moved from and to (``from_stage`` / ``to_stage``; the
  initial "creation" log row has ``from_stage IS NULL``),
* who triggered the change (``changed_by_user_id``),
* when it happened (``changed_at``).

The model is tenant-scoped via :class:`TenantScopedBase` so the unique
ADR-0001 rule (every table carries ``tenant_id``) holds, and so that
``apply_tenant_scope`` automatically confines application-stage-history
queries to the caller's tenant.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage


class StageHistory(TenantScopedBase):
    """Append-only stage transition log for an application (E25; Journey J18)."""

    __tablename__ = "stage_history"

    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # NULL when logging the application's initial creation (no prior stage).
    from_stage: Mapped[PipelineStage | None] = mapped_column(
        Enum(
            PipelineStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    to_stage: Mapped[PipelineStage] = mapped_column(
        Enum(
            PipelineStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    changed_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
