"""Document checklist template model (E15 schema + E26 read model).

This module owns the *template* half of the E26
``GET /applications/{application_id}/checklist`` endpoint ("merges
template + upload status", Journey J19). The full CRUD for these
templates lands in E15 (Document Checklist Template Management); here
we only need the persisted shape so the read API can return the merged
view.

Design (Requirements §5; Journey J8; Epic E15; Epic E26):

* Tenant-scoped (ADR-0001: every table has ``tenant_id``). Inherited
  from :class:`TenantScopedBase`.
* ``stage`` is a :class:`PipelineStage` value (e.g. ``document_verification``).
  Templates are defined per stage so the checklist view can change as the
  application advances through the pipeline.
* ``program_id`` is nullable and FK-loose: a NULL ``program_id`` means the
  template applies to *every* program in the tenant (the common case for
  documents like "passport" or "transcripts"). A non-NULL ``program_id``
  narrows the template to a specific :class:`Program` row.
* ``name`` is the human-readable label shown on the student's checklist
  (e.g. "10th-grade transcripts"). ``description`` is optional and may
  hold longer guidance.
* ``required`` is the boolean flag distinguishing "must upload" from
  "optional" checklist items.
* ``order_index`` is a small int for stable UI ordering (NULL = append).

The companion :class:`StudentDocument` model (same module family)
records the student's actual uploads against a template row, with a
``status`` enum (pending/approved/rejected). E26's retrieval endpoint
joins the two and returns the merged view required by Journey J19.
"""

from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage

__all__ = ["ChecklistItemTemplate"]


class ChecklistItemTemplate(TenantScopedBase):
    """A required-or-optional document on a stage/program's checklist (E15; E26).

    See module docstring for design rationale. A row is the "shape" of
    a checklist item; the actual student-uploaded artifact is captured
    by :class:`StudentDocument.checklist_item_template_id`.
    """

    __tablename__ = "checklist_item_templates"

    stage: Mapped[PipelineStage] = mapped_column(
        Enum(
            PipelineStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        index=True,
    )
    program_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
