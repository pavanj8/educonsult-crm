"""Student document upload model (E27 schema + E26 read model; issue #174;
E29 / J22 ``approval_comment`` column added in issue #181;
E31 / J24 ``supersedes_id`` column added in issue #187).

This module owns the *upload status* half of the E26
``GET /applications/{application_id}/checklist`` endpoint ("merges
template + upload status", Journey J19) and the E27 student document
upload flow (Journey J20). The actual file upload API,
S3-compatible storage integration, and 10MB/PDF/JPG/PNG/DOCX validation
land in sibling tickets #175 / #176; here we only need the persisted
shape so the read API can report each upload's status and the upload
API can persist new rows against a checklist item.

Design (Requirements §5; Journey J19–J24; Epic E27; Epic E26; Epic E29;
Epic E31):

* Tenant-scoped (ADR-0001: every table has ``tenant_id``). Inherited
  from :class:`TenantScopedBase`.
* ``application_id`` FKs the :class:`Application` row this upload
  belongs to; combined with tenant scoping this is the primary access
  pattern for E26's checklist read.
* ``checklist_item_template_id`` is a nullable FK to
  :class:`ChecklistItemTemplate` — nullable so E31 (re-upload flow)
  can attach an upload to a previously rejected item without forcing
  the upload to come from a checklist row. A NULL value simply means
  "upload not tied to a checklist row" (an edge case; the E26 read
  endpoint still surfaces such uploads under the application's
  "uncategorized" view if needed).
* ``status`` is a small enum capturing the verifier's decision
  (Journey J22 approve / J23 reject / J20 upload = pending). It is the
  field the E26 endpoint surfaces as ``upload_status`` to the frontend.
* ``original_filename`` / ``content_type`` / ``size_bytes`` /
  ``storage_path`` are the minimum metadata needed to render an
  upload in the checklist UI and for E27's future file-serving API.
* ``uploaded_by_user_id`` records who performed the upload (always
  the student today; the column is kept for audit + future
  staff-on-behalf-of-student flows). ``uploaded_at`` is the
  explicit event timestamp.
* ``verified_by_user_id`` (nullable, ON DELETE SET NULL) and
  ``verified_at`` capture the verifier's action for the audit trail
  required by Requirements §8.
* ``rejection_reason`` is the free-text comment recorded by the
  verifier on reject (Journey J23). NULL when ``status`` is not
  ``rejected``.
* ``approval_comment`` is the parallel free-text comment recorded by
  the verifier on approve (Journey J22; E29 backend ticket #181).
  NULL when ``status`` is not ``approved``. Kept as a separate column
  from ``rejection_reason`` so the two audit trails remain distinct
  and the model keeps an obvious 1:1 mapping between status value and
  comment column.
* ``supersedes_id`` is a nullable self-FK to another
  :class:`StudentDocument` row (ON DELETE SET NULL). Non-NULL only
  when this upload was created as a *re-upload* of a previously
  rejected document (Journey J24 / Epic E31 / issue #187). The link
  is what turns the re-upload from "yet another pending row" into a
  versioned replacement with a preserved audit trail (Requirements
  §8 — audit log on key actions such as document approvals); the
  superseded row stays in the table with its original
  ``status='rejected'`` so the verifier's earlier decision and
  ``rejection_reason`` are not lost. The column is nullable because
  initial uploads have no predecessor.
"""

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

__all__ = ["StudentDocument", "StudentDocumentStatus"]


class StudentDocumentStatus(StrEnum):
    """Verification status of a student document upload (Journey J20; J22; J23).

    * ``pending`` — student has uploaded; verifier has not yet acted.
    * ``approved`` — verifier approved the upload (Journey J22).
    * ``rejected`` — verifier rejected with a ``rejection_reason``
      (Journey J23).
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StudentDocument(TenantScopedBase):
    """A student's uploaded document (E27; E26 read model; Journey J20).

    The ``supersedes_id`` column (added by issue #187 / E31) links a
    re-upload to the rejected :class:`StudentDocument` it replaces;
    see the module docstring for the full design.
    """

    __tablename__ = "student_documents"

    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checklist_item_template_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("checklist_item_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[StudentDocumentStatus] = mapped_column(
        Enum(
            StudentDocumentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=StudentDocumentStatus.PENDING,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    verified_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approval_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # E31 / issue #187: nullable self-FK for re-upload audit trail.
    # ON DELETE SET NULL so deleting a previously-rejected row does not
    # cascade-delete the re-upload that replaced it (an admin action on
    # one row must not destroy the next version's audit chain).
    supersedes_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("student_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
