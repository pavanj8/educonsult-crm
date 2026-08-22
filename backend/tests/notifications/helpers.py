"""Test helpers for the notification center API tests (E50;
Journey J43; issue #236).

Centralised so each ``test_*.py`` file in this package can seed
notification rows without re-implementing the raw insert.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.notification import Notification


def seed_notification(
    db_session,
    *,
    user_id: int,
    title: str,
    message: str,
    tenant_id: int = 1,
    read_at: datetime | None = None,
    created_at: datetime | None = None,
) -> int:
    """Insert a :class:`Notification` row and return its id."""
    created = created_at or datetime.now(timezone.utc)
    row = Notification(
        user_id=user_id,
        tenant_id=tenant_id,
        title=title,
        message=message,
        read_at=read_at,
        created_at=created,
        updated_at=created,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row.id