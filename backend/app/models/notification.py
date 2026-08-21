"""In-app notification model (E48; Journey J41; issue #229).

A notification row represents a single in-app notification generated
on a relevant event for a specific recipient (the authenticated user
who should see it in their notification center — E50). Today this
table only carries the data needed to render the in-app entry; the
E49 email side and the E50 read/mark-read flows are siblings.

Design (Requirements §6 Notifications; Journey J41; Epic E48):

* Tenant-scoped (ADR-0001: every table carries ``tenant_id``). Inherited
  from :class:`TenantScopedBase`, which also provides ``id``,
  ``created_at``, and ``updated_at``.
* ``user_id`` is the recipient (the user who should see this
  notification in their center). A nullable FK with
  ``ON DELETE SET NULL`` so deleting a user does not cascade-delete
  their notification history (audit considerations).
* ``event_type`` is a short string key identifying the originating
  event (e.g. ``"application.stage_advanced"``, ``"document.approved"``,
  ``"document.rejected"``, ``"application.created"``,
  ``"application.counselor_assigned"``). The set of event types is
  documented in :data:`app.services.notifications.EVENT_*` constants
  and stays intentionally small / explicit so the frontend can route /
  icon them.
* ``title`` / ``message`` are pre-rendered, human-readable strings
  (English only for v1; i18n is E51's territory). They are stored on
  the row so the read endpoint (E50) can serve them without joining
  back to the source tables.
* ``read_at`` is ``NULL`` while the notification is unread, and is
  set to the UTC timestamp the user marks it read via the E50 mark-
  read endpoint.
* ``related_application_id`` / ``related_document_id`` /
  ``related_stage_history_id`` are nullable convenience FKs the E50
  read endpoint can use to deep-link into the right page. They are
  all ``ON DELETE SET NULL`` so the notification survives deletion
  of the originating row.
* Indexes target the primary access patterns: per-user unread counts
  and the E50 list-by-user query (orderable by ``created_at``).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

__all__ = ["Notification"]


class Notification(TenantScopedBase):
    """A single in-app notification row (E48; Journey J41; issue #229)."""

    __tablename__ = "notifications"

    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    related_application_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    related_document_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("student_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_stage_history_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("stage_history.id", ondelete="SET NULL"),
        nullable=True,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_notifications_tenant_user_unread",
            "tenant_id",
            "user_id",
        ),
    )
