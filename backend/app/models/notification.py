"""In-app notification model (E48 schema; Journey J41).

Each row is a single in-app notification delivered to a user on a
relevant event (Requirements §6: "In-app + email for status changes,
document verification results, meeting scheduling"). The notification
center UI (E50; Journey J43) renders a user's rows here, and the
notification-creation service + hooks that *populate* this table land
in the sibling E48 task. This ticket owns the schema only.

Design (Requirements §6; Journey J41; Epic E48):

* Tenant-scoped (ADR-0001: every table carries ``tenant_id``).
  Inherited from :class:`TenantScopedBase`, which also provides
  ``id``, ``created_at``, and ``updated_at``.
* ``user_id`` is the recipient of the notification. FK to ``users``
  with ``ON DELETE CASCADE`` so deleting a user account also clears
  their in-app notifications (a user with no account has no inbox).
* ``title`` is the short heading shown in the notification center UI
  (frontend ``Notification.title`` field).
* ``message`` is the body of the notification (frontend
  ``Notification.message`` field). Free-text so individual event
  types can include relevant detail (e.g. document review comments).
* ``read_at`` is the nullable timestamp set when the user marks the
  notification read (Journey J43). NULL = unread.
* ``application_id`` is an optional FK to :class:`Application` so the
  notification can deep-link back to the relevant application.
  Nullable because not every event is tied to an application
  (e.g. tenant-level announcements).

Indexes target the primary access pattern: per-user list queries
("notification center" list, J43) and per-tenant audit. The
composite of ``user_id`` + ``read_at`` is not indexed here -- the
list endpoint that lands in E50 (#232) decides whether to add one
based on its filter needs.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

__all__ = ["Notification"]


class Notification(TenantScopedBase):
    """An in-app notification row for a single user (E48; Journey J41)."""

    __tablename__ = "notifications"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    application_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )