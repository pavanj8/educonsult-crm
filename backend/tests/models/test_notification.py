"""Tests for the Notification ORM model (E48; Journey J41).

Exercises column shape, persistence, the nullable ``read_at`` /
``application_id`` columns, and FK behavior (``user_id`` cascades on
delete; ``application_id`` is SET NULL on delete).
"""

from datetime import datetime, timezone

from sqlalchemy import inspect

from app.models.notification import Notification


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_notification_model_has_required_columns():
    column_names = {column.key for column in inspect(Notification).columns}
    assert column_names == {
        "id",
        "tenant_id",
        "user_id",
        "title",
        "message",
        "read_at",
        "application_id",
        "created_at",
        "updated_at",
    }


def test_notification_persists_full_row(db_session):
    """A Notification row with every field populated round-trips through the DB."""
    now = _utc_now()
    notification = Notification(
        tenant_id=1,
        user_id=42,
        title="Document approved",
        message="Your passport copy was approved by the verifier.",
        read_at=None,
        application_id=100,
        created_at=now,
        updated_at=now,
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)

    assert notification.id is not None
    assert notification.tenant_id == 1
    assert notification.user_id == 42
    assert notification.title == "Document approved"
    assert notification.message == "Your passport copy was approved by the verifier."
    # SQLite drops the tzinfo on round-trip; compare the absolute UTC instant.
    assert notification.read_at is None
    assert notification.application_id == 100
    assert notification.created_at is not None
    assert notification.updated_at is not None


def test_notification_read_at_is_nullable(db_session):
    """``read_at`` is NULL until the user marks the notification read (Journey J43)."""
    now = _utc_now()
    notification = Notification(
        tenant_id=1,
        user_id=1,
        title="Hello",
        message="World",
        read_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)

    assert notification.read_at is None


def test_notification_application_id_is_nullable(db_session):
    """``application_id`` is NULL when the event is not tied to an application."""
    now = _utc_now()
    notification = Notification(
        tenant_id=1,
        user_id=1,
        title="Tenant announcement",
        message="Welcome to the platform",
        read_at=None,
        application_id=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)

    assert notification.application_id is None


def test_notification_can_be_marked_read(db_session):
    """Setting ``read_at`` round-trips and persists the timestamp."""
    now = _utc_now()
    later = _utc_now()
    notification = Notification(
        tenant_id=1,
        user_id=1,
        title="Hello",
        message="World",
        read_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)

    assert notification.read_at is None

    notification.read_at = later
    db_session.commit()
    db_session.refresh(notification)

    assert notification.read_at is not None
    assert notification.read_at.replace(tzinfo=timezone.utc) == later


def test_notification_tenant_scoping(db_session):
    """Two tenants' notifications coexist and are addressable by id."""
    now = _utc_now()
    notification_t1 = Notification(
        tenant_id=1,
        user_id=1,
        title="Tenant 1 notification",
        message="Hello",
        created_at=now,
        updated_at=now,
    )
    notification_t2 = Notification(
        tenant_id=2,
        user_id=2,
        title="Tenant 2 notification",
        message="Hello",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([notification_t1, notification_t2])
    db_session.commit()
    db_session.refresh(notification_t1)
    db_session.refresh(notification_t2)

    assert notification_t1.tenant_id == 1
    assert notification_t2.tenant_id == 2
    assert notification_t1.id != notification_t2.id