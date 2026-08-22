"""Notification center list / mark-read API (E50; Journey J43; issue #236).

This router is the backend half of the notification center UX. The
frontend notification bell + notification center UI (sibling ticket
#237) calls these three endpoints:

* ``GET /notifications`` -- return the caller's notifications in
  created-desc order, plus an ``unread_count`` summary the bell uses
  to render its badge.
* ``PATCH /notifications/{notification_id}/read`` -- mark a single
  notification as read; idempotent (already-read rows return 200 with
  the existing ``read_at`` unchanged).
* ``PATCH /notifications/read-all`` -- mark every one of the caller's
  unread notifications as read in a single round-trip (used by the
  notification center's "Mark all as read" action).

Authorization
-------------
All endpoints require a valid access token (any authenticated user)
and require the ``notification:read`` permission, which is granted
to every role in
:data:`app.rbac.permissions.ROLE_PERMISSIONS` (the notification
center is a universal cross-role surface per Requirements §6 /
Journey J43). The list is always filtered by the caller's
``user_id`` -- users never receive another user's notifications and
cross-tenant access surfaces as 404 (no enumeration).

Errors
------
* 401 -- caller is not authenticated.
* 403 -- caller lacks the ``notification:read`` permission (defence
  in depth; in practice every role is granted it).
* 404 -- ``PATCH /notifications/{id}/read`` for a notification that
  does not exist or does not belong to the caller.
* 503 -- database unavailable while reading / writing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.notification import Notification
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.notification import NotificationItem, NotificationListResponse

router = APIRouter()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_DB_UNAVAILABLE_DETAIL = "Notification service is temporarily unavailable"


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.NOTIFICATION_READ)),
    ],
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    """Return the caller's notifications in created-desc order.

    The list is always scoped to ``current_user.id`` (and, where
    applicable, ``current_user.tenant_id``) so users never see
    another user's notifications. ``unread_count`` is the number of
    the caller's notifications with ``read_at IS NULL``.
    """
    base_filters = [Notification.user_id == current_user.id]
    if current_user.tenant_id is not None:
        base_filters.append(Notification.tenant_id == current_user.tenant_id)

    try:
        unread_count = db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(*base_filters)
            .where(Notification.read_at.is_(None))
        ) or 0
        rows = db.scalars(
            select(Notification)
            .where(*base_filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
        ).all()
    except OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from exc

    return NotificationListResponse(
        items=[NotificationItem.model_validate(row) for row in rows],
        unread_count=unread_count,
    )


def _get_own_notification(
    notification_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> Notification:
    """Load a notification belonging to the caller, or raise 404.

    Cross-user and cross-tenant access both surface as 404 to avoid
    letting a hostile client enumerate other users' notification ids
    by probing the endpoint (mirrors the tenant-scoping convention
    used by :func:`app.routers.verifier._get_tenant_document`).
    """
    try:
        notification = db.get(Notification, notification_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    if (
        current_user.tenant_id is not None
        and notification.tenant_id != current_user.tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return notification


@router.patch("/{notification_id}/read", response_model=NotificationItem)
def mark_notification_read(
    notification_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.NOTIFICATION_READ)),
    ],
    db: Session = Depends(get_db),
) -> Notification:
    """Mark a single notification as read (E50; J43).

    Idempotent: a notification already marked read is returned with
    its existing ``read_at`` unchanged (HTTP 200). The first call
    that flips a row from unread to read sets ``read_at`` to the
    current UTC timestamp.
    """
    notification = _get_own_notification(notification_id, current_user, db)

    if notification.read_at is None:
        notification.read_at = _utc_now()
        try:
            db.commit()
        except OperationalError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_DB_UNAVAILABLE_DETAIL,
            ) from None
        db.refresh(notification)

    return notification


@router.patch("/read-all", response_model=NotificationListResponse)
def mark_all_notifications_read(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.NOTIFICATION_READ)),
    ],
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    """Mark every one of the caller's unread notifications as read.

    Returns the post-mutation list (with ``unread_count`` necessarily
    0) so the UI can refresh its state without a second round-trip
    to ``GET /notifications``. Already-read notifications are left
    untouched (their ``read_at`` is preserved verbatim).
    """
    base_filters = [Notification.user_id == current_user.id]
    if current_user.tenant_id is not None:
        base_filters.append(Notification.tenant_id == current_user.tenant_id)

    try:
        unread_rows = db.scalars(
            select(Notification)
            .where(*base_filters)
            .where(Notification.read_at.is_(None))
        ).all()
        now = _utc_now()
        for row in unread_rows:
            row.read_at = now
        if unread_rows:
            db.commit()
            for row in unread_rows:
                db.refresh(row)

        rows = db.scalars(
            select(Notification)
            .where(*base_filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
        ).all()
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from exc

    return NotificationListResponse(
        items=[NotificationItem.model_validate(row) for row in rows],
        unread_count=0,
    )