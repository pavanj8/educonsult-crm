"""PATCH /notifications/read-all endpoint tests (E50; Journey J43;
issue #236).

Covers happy-path mark-all-read, preservation of already-read
``read_at`` timestamps, isolation from other users' notifications,
empty-inbox behaviour, and the unauthenticated 401 response.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.notification import Notification
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user, make_db_user
from tests.notifications.helpers import seed_notification


def test_mark_all_notifications_read_marks_every_unread(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    seed_notification(db_session, user_id=me.id, title="u1", message="m1")
    seed_notification(db_session, user_id=me.id, title="u2", message="m2")
    seed_notification(db_session, user_id=me.id, title="u3", message="m3")
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.patch("/notifications/read-all")

    assert response.status_code == 200
    body = response.json()
    assert body["unread_count"] == 0
    assert len(body["items"]) == 3
    assert all(item["read_at"] is not None for item in body["items"])


def test_mark_all_notifications_read_preserves_existing_read_at(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    original_read_at = datetime.now(timezone.utc) - timedelta(days=2)
    seed_notification(
        db_session,
        user_id=me.id,
        title="already-read",
        message="m",
        read_at=original_read_at,
    )
    seed_notification(db_session, user_id=me.id, title="unread", message="m")
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.patch("/notifications/read-all")

    assert response.status_code == 200
    body = response.json()
    already_read_item = next(
        item for item in body["items"] if item["title"] == "already-read"
    )
    returned_read_at = datetime.fromisoformat(already_read_item["read_at"])
    if returned_read_at.tzinfo is None:
        returned_read_at = returned_read_at.replace(tzinfo=timezone.utc)
    assert abs((returned_read_at - original_read_at).total_seconds()) < 1
    assert body["unread_count"] == 0


def test_mark_all_notifications_read_does_not_touch_other_users(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    other = make_db_user(db_session, Role.STUDENT, email="other@example.test", tenant_id=1)
    seed_notification(db_session, user_id=me.id, title="mine", message="m")
    other_notification_id = seed_notification(
        db_session, user_id=other.id, title="theirs", message="m"
    )
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.patch("/notifications/read-all")

    assert response.status_code == 200
    assert response.json()["unread_count"] == 0

    stored = db_session.execute(
        select(Notification).where(Notification.id == other_notification_id)
    ).scalar_one()
    assert stored.read_at is None


def test_mark_all_notifications_read_with_empty_inbox_is_noop(
    client, db_session, override_authenticated_user
):
    make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=1, tenant_id=1)
    )

    response = client.patch("/notifications/read-all")

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["unread_count"] == 0


def test_mark_all_notifications_read_rejects_unauthenticated_request(client):
    response = client.patch("/notifications/read-all")

    assert response.status_code == 401