"""PATCH /notifications/{id}/read endpoint tests (E50; Journey J43;
issue #236).

Covers happy-path mark-read, idempotency, cross-user / cross-tenant
404 behaviour, unknown-id 404, and the unauthenticated 401
response.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.notification import Notification
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user, make_db_user
from tests.notifications.helpers import seed_notification


def test_mark_notification_read_sets_read_at_and_returns_row(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    notification_id = seed_notification(db_session, user_id=me.id, title="t", message="m")
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.patch(f"/notifications/{notification_id}/read")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == notification_id
    assert body["read_at"] is not None

    listed = client.get("/notifications").json()
    assert listed["unread_count"] == 0
    assert listed["items"][0]["read_at"] is not None


def test_mark_notification_read_is_idempotent(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    original_read_at = datetime.now(timezone.utc) - timedelta(hours=1)
    notification_id = seed_notification(
        db_session,
        user_id=me.id,
        title="t",
        message="m",
        read_at=original_read_at,
    )
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.patch(f"/notifications/{notification_id}/read")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == notification_id
    returned_read_at = datetime.fromisoformat(body["read_at"])
    if returned_read_at.tzinfo is None:
        returned_read_at = returned_read_at.replace(tzinfo=timezone.utc)
    assert abs((returned_read_at - original_read_at).total_seconds()) < 1


def test_mark_notification_read_rejects_other_users_notification(
    client, db_session, override_authenticated_user
):
    other = make_db_user(db_session, Role.STUDENT, email="other@example.test", tenant_id=1)
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    other_notification_id = seed_notification(
        db_session, user_id=other.id, title="not-mine", message="m"
    )
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.patch(f"/notifications/{other_notification_id}/read")

    assert response.status_code == 404
    assert response.json()["detail"] == "Notification not found"

    stored = db_session.execute(
        select(Notification).where(Notification.id == other_notification_id)
    ).scalar_one()
    assert stored.read_at is None


def test_mark_notification_read_rejects_other_tenants_notification(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    notification_id = seed_notification(
        db_session,
        user_id=me.id,
        tenant_id=2,
        title="cross-tenant",
        message="m",
    )
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.patch(f"/notifications/{notification_id}/read")

    assert response.status_code == 404


def test_mark_notification_read_returns_404_for_unknown_id(
    client, db_session, override_authenticated_user
):
    make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=1, tenant_id=1)
    )

    response = client.patch("/notifications/99999/read")

    assert response.status_code == 404


def test_mark_notification_read_rejects_unauthenticated_request(
    client, db_session
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    notification_id = seed_notification(
        db_session, user_id=me.id, title="t", message="m"
    )

    response = client.patch(f"/notifications/{notification_id}/read")

    assert response.status_code == 401