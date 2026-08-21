<<<<<<< HEAD
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
=======
"""Application stage history audit log model (E25; Journey J18).

Each row is a single recorded stage transition for an application,
captured by the ``advance-stage`` flow that lands in a follow-up E25
ticket. This ticket owns the schema only -- the runtime logging path
that inserts rows here is wired up in the ``advance-stage API with
history logging`` task.

Design (Requirements §5; Journey J18; Epic E25):

* Tenant-scoped (ADR-0001: every table has ``tenant_id``). Inherited
  from :class:`TenantScopedBase`, which also provides ``id``,
  ``created_at``, and ``updated_at``.
* ``from_stage`` is nullable so the first row for a newly-created
  application can record the initial ``REGISTERED`` provenance with
  no prior stage.
* ``to_stage`` is the resulting stage after the transition.
* ``changed_by_user_id`` is nullable with ``ON DELETE SET NULL`` so
  deleting a staff account does not cascade-delete their audit trail.
* ``changed_at`` is the explicit event timestamp (mirrors the
  Requirements §8 audit-log style of "when did this happen") and is
  separate from the inherited ``created_at``/``updated_at`` so the row
  is orderable by event time even if the SQLAlchemy bookkeeping later
  mutates ``updated_at``.
* ``reason`` is the optional free-text reason required for the three
  terminal stages (Requirements §5: "Enrolled / Rejected / Withdrawn,
  three distinct terminal states, each capturing a reason" -- the
  reason is captured on the REJECTED / WITHDRAWN paths per J32 / J33,
  and may be NULL for ordinary forward pipeline moves).
* Indexes target the primary access patterns: lookups by application
  (stage timeline) and by tenant (tenant-scoped audit queries).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text
>>>>>>> origin/main
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage

<<<<<<< HEAD

class StageHistory(TenantScopedBase):
    """Append-only stage transition log for an application (E25; Journey J18)."""
=======
__all__ = ["StageHistory"]


class StageHistory(TenantScopedBase):
    """Audit log row recording a single application stage transition (E25; J18)."""
>>>>>>> origin/main

    __tablename__ = "stage_history"

    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
<<<<<<< HEAD
    # NULL when logging the application's initial creation (no prior stage).
    from_stage: Mapped[PipelineStage | None] = mapped_column(
=======
    from_stage: Mapped[Optional[PipelineStage]] = mapped_column(
>>>>>>> origin/main
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
<<<<<<< HEAD
    changed_by_user_id: Mapped[int] = mapped_column(
=======
    changed_by_user_id: Mapped[Optional[int]] = mapped_column(
>>>>>>> origin/main
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
<<<<<<< HEAD
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
=======
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
>>>>>>> origin/main
