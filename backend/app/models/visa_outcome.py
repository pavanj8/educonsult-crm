"""Visa outcome model (E35; Journey J28).

Persists the visa outcome/status recorded by a Visa Processor against
an application whose pipeline stage is ``visa_processing``
(Requirements §5: per-application pipeline stages; see
:class:`app.pipeline.stages.PipelineStage`). The Visa Processor
updates this via the visa outcome update API (E35; issue #195) and
the corresponding frontend UI (#196, in progress).

Design (Requirements §3 Visa Processor role; §5 Student Journey &
Data Model; Journey J28 "Visa Processor updates visa outcome/status";
Epic E35; ADR-0001):

* Tenant-scoped (ADR-0001: every table carries ``tenant_id``).
  Inherited from :class:`TenantScopedBase`, which also provides
  ``id``, ``created_at``, and ``updated_at``.
* ``application_id`` is a 1:1 FK to :class:`Application` and the
  column is uniquely constrained so a single application can carry
  at most one :class:`VisaOutcome` row. This matches J28's phrasing
  ("Visa Processor updates visa outcome/status") -- the outcome is
  a property of *the* application at the visa stage, not a list of
  historical entries. ON DELETE CASCADE mirrors the E34
  :class:`VisaDetail` FK convention so deleting an application also
  clears its visa outcome.
* ``status`` is the recorded outcome label (e.g. ``"approved"``,
  ``"rejected"``). Modelled as a short ``String`` rather than an
  enum because the catalogue of visa outcomes may evolve (an
  ``"on_hold"`` or ``"rescheduled"`` state could later be added)
  and the v1 spec does not promise an admin-managed master list of
  outcomes -- the spec lists master data only for countries /
  universities / programs (Journey J7). The 32-char length is
  comfortably larger than any realistic outcome label.
* ``outcome_date`` is the date the outcome was decided (Journey
  J28). It is timezone-aware (``DateTime(timezone=True)``) because
  embassies span many time zones and the J28 audit-log story
  (Requirements §8) wants a precise instant rather than a naive
  date. Nullable so the visa processor can save a draft outcome
  before committing to an outcome date.
* ``notes`` is optional free-text detail the visa processor
  records alongside the outcome (e.g. embassy interview
  comments). Modelled as ``Text`` to mirror the E39
  ``MarkRejectedRequest.reason`` ceiling, which is a free-form
  string up to 2000 characters.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

__all__ = ["VisaOutcome"]


class VisaOutcome(TenantScopedBase):
    """Visa outcome/status for an application (E35; Journey J28).

    One row per application; the unique constraint on
    ``application_id`` enforces that. Deleting an application also
    deletes its :class:`VisaOutcome` row (CASCADE).
    """

    __tablename__ = "visa_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            name="uq_visa_outcomes_application_id",
        ),
    )

    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
