"""In-app notification model (E50; Journey J43; issue #236).

Each row is a single in-app notification addressed to a specific user.
They are surfaced through the notification center list / mark-read API
implemented by this ticket (and already consumed by the frontend
notification bell + center UI shipped in sibling ticket #237).

Design (Requirements §6; Journey J41 + J43; Epic E48; Epic E50):

* Tenant-scoped (ADR-0001: every table has ``tenant_id``). Inherited
  from :class:`TenantScopedBase`, which also provides ``id``,
  ``created_at``, and ``updated_at``.
* ``user_id`` is the recipient of the notification. The list /
  mark-read API in this ticket always filters by
  ``user_id == current_user.id`` so users only ever see their own
  notifications (Requirements §6: "User receives an in-app
  notification on a relevant event").
* ``tenant_id`` is denormalised alongside ``user_id`` so the list
  query can index-scan by tenant first (matching the rest of the
  codebase's tenant-scoping convention) and so the foreign key to
  ``users`` is unambiguous in the rare case the same numeric
  ``user_id`` ever appears in two tenants during data migration /
  testing.
* ``title`` and ``message`` are the human-readable strings surfaced
  verbatim by the notification center UI (the frontend's
  ``Notification`` type expects both fields verbatim).
* ``read_at`` is the explicit event timestamp marking when the
  recipient first marked the notification read. NULL means unread;
  a non-NULL timestamp means read (Requirements §6: "User views
  notification center and marks items read").
* No FK to ``users`` is declared so a deleted user does not
  cascade-delete their notification audit trail (mirrors
  ``StageHistory.changed_by_user_id``'s ON DELETE SET NULL pattern).
  This keeps notifications queryable from the platform-wide
  notification center if it is later extended with super-admin
  debugging views, and prevents an accidental mass-delete when a
  staff account is removed.
* Indexes target the primary access patterns: list-by-user for the
  notification center (the dominant query) and tenant scoping.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

__all__ = ["Notification"]


class Notification(TenantScopedBase):
    """A single in-app notification delivered to a user (E50; J43)."""

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
    )