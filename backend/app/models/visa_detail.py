"""Visa detail model (E34; Journey J27).

Persists the visa type and embassy interview date recorded by a Visa
Processor against an application whose pipeline stage is
``visa_processing`` (Requirements §5: per-application pipeline stages;
see :class:`app.pipeline.stages.PipelineStage`). The Visa Processor
records these via the frontend visa detail update form (issue #194);
the recording API itself is wired up in that sibling ticket. This
module owns only the persisted shape so the migration can land in
parallel with the frontend work and the API can read and write
against a stable table.

Design (Requirements §3 Visa Processor role; §5 Student Journey &
Data Model; Journey J27 "Visa Processor records visa type & embassy
interview date"; Epic E34; ADR-0001):

* Tenant-scoped (ADR-0001: every table carries ``tenant_id``).
  Inherited from :class:`TenantScopedBase`, which also provides
  ``id``, ``created_at``, and ``updated_at``.
* ``application_id`` is a 1:1 FK to :class:`Application` and the
  column is uniquely constrained so a single application can carry
  at most one :class:`VisaDetail` row. This matches J27's phrasing
  ("Visa Processor records visa type & embassy interview date") —
  the visa type and interview date are properties of *the*
  application at the visa stage, not a list of historical entries.
  ON DELETE CASCADE mirrors the meeting / note / document FK
  convention so deleting an application also clears its visa detail.
* ``visa_type`` is the free-text / structured label the visa
  processor records (e.g. "F-1 Student", "Tier 4 Student"). It is
  modelled as a short ``String`` rather than an enum because the
  catalogue of visa types varies by destination country and target
  program, and the v1 spec does not promise an admin-managed master
  list of visa types — the spec lists master data only for
  countries / universities / programs (Journey J7). The E34 frontend
  ticket (#194) is free to back this with a dropdown sourced from
  E14 master data once that lands; until then the column accepts
  whatever string the visa processor enters. The 100-char length
  mirrors the ``StudentDocument.original_filename`` ceiling and is
  comfortably larger than any realistic visa-type label.
* ``interview_date`` is the date of the embassy interview (Journey
  J27). It is timezone-aware (``DateTime(timezone=True)``) because
  embassies span many time zones and the J27 notification/calendar
  story (E48 in-app notifications for visa events) wants a precise
  instant rather than a naive date. Nullable so the visa processor
  can record the visa type ahead of the interview date — J27
  describes them as two fields the processor fills in over time,
  not as a single atomic entry.
* Outcome fields (``status``, ``outcome_date``, ``notes``) are
  intentionally NOT modelled here. Outcome capture is the E35
  (Visa Outcome Update) ticket (Journey J28) and lives on its own
  schema to avoid pre-empting those decisions.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

__all__ = ["VisaDetail"]


class VisaDetail(TenantScopedBase):
    """Visa type + embassy interview date for an application (E34; Journey J27).

    One row per application; the unique constraint on
    ``application_id`` enforces that. Deleting an application also
    deletes its :class:`VisaDetail` row (CASCADE). Outcome fields are
    out of scope for E34 and live on the E35 (Journey J28) follow-up.
    """

    __tablename__ = "visa_details"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            name="uq_visa_details_application_id",
        ),
    )

    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visa_type: Mapped[str] = mapped_column(String(100), nullable=False)
    interview_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )