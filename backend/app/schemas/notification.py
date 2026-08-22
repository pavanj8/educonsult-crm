"""Pydantic schemas for the notification center API (E50; Journey J43;
issue #236).

Shapes mirror the frontend's ``Notification`` /
``NotificationListResponse`` types verbatim so the API can be called
1:1 by the notification bell + notification center UI shipped in
sibling ticket #237 without any client-side translation:

* :class:`NotificationItem` -- a single notification row, surfaced
  verbatim by ``GET /notifications`` (list) and as the body of
  ``PATCH /notifications/{notification_id}/read`` (mark read).
* :class:`NotificationListResponse` -- the list endpoint's body, with
  ``items`` (in created-desc order) and ``unread_count`` (number of
  items with ``read_at IS NULL``) so the bell can render its badge
  in a single round-trip.

The endpoint surfaces only the fields the UI already consumes
(``id``, ``title``, ``message``, ``read_at``, ``created_at``);
internal fields like ``tenant_id`` / ``user_id`` are deliberately
omitted from the response (they are server-internal scoping
metadata, not user-visible state).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationItem(BaseModel):
    """A single notification surfaced to a user in the notification center."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Response body for ``GET /notifications``.

    ``items`` is the user's notifications in created-desc order.
    ``unread_count`` is the number of items whose ``read_at`` is NULL,
    so the bell badge stays in sync with the list without a second
    round-trip.
    """

    items: list[NotificationItem]
    unread_count: int


__all__ = ["NotificationItem", "NotificationListResponse"]