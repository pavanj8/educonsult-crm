"""GET /notifications endpoint tests (E50; Journey J43; issue #236).

Covers user-scoped list, tenant scoping, ordering, unread count,
empty-inbox, the public response shape, and the unauthenticated
401 response.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user, make_db_user
from tests.notifications.helpers import seed_notification


def test_list_notifications_returns_only_callers_notifications(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    other = make_db_user(db_session, Role.STUDENT, email="other@example.test", tenant_id=1)
    seed_notification(db_session, user_id=me.id, title="Mine A", message="m-a")
    seed_notification(db_session, user_id=me.id, title="Mine B", message="m-b")
    seed_notification(db_session, user_id=other.id, title="Theirs", message="not-mine")
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.get("/notifications")

    assert response.status_code == 200
    body = response.json()
    titles = {item["title"] for item in body["items"]}
    assert titles == {"Mine A", "Mine B"}
    assert body["unread_count"] == 2


def test_list_notifications_excludes_other_tenants(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    seed_notification(
        db_session,
        user_id=me.id,
        tenant_id=2,
        title="Other tenant",
        message="cross-tenant",
    )
    seed_notification(
        db_session,
        user_id=me.id,
        tenant_id=1,
        title="Mine",
        message="in-tenant",
    )
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.get("/notifications")

    assert response.status_code == 200
    body = response.json()
    titles = {item["title"] for item in body["items"]}
    assert titles == {"Mine"}
    assert body["unread_count"] == 1


def test_list_notifications_orders_newest_first(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    now = datetime.now(timezone.utc)
    seed_notification(
        db_session,
        user_id=me.id,
        title="older",
        message="o",
        created_at=now - timedelta(minutes=10),
    )
    seed_notification(
        db_session,
        user_id=me.id,
        title="newest",
        message="n",
        created_at=now,
    )
    seed_notification(
        db_session,
        user_id=me.id,
        title="middle",
        message="m",
        created_at=now - timedelta(minutes=5),
    )
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.get("/notifications")

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["newest", "middle", "older"]


def test_list_notifications_unread_count_excludes_read_items(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    seed_notification(
        db_session,
        user_id=me.id,
        title="r1",
        message="m1",
        read_at=datetime.now(timezone.utc),
    )
    seed_notification(
        db_session,
        user_id=me.id,
        title="r2",
        message="m2",
        read_at=datetime.now(timezone.utc),
    )
    seed_notification(db_session, user_id=me.id, title="u1", message="m3")
    seed_notification(db_session, user_id=me.id, title="u2", message="m4")
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.get("/notifications")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 4
    assert body["unread_count"] == 2


def test_list_notifications_empty_inbox_returns_empty_list(
    client, db_session, override_authenticated_user
):
    make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=1, tenant_id=1)
    )

    response = client.get("/notifications")

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["unread_count"] == 0


def test_list_notifications_rejects_unauthenticated_request(client):
    response = client.get("/notifications")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_list_notifications_returns_expected_fields(
    client, db_session, override_authenticated_user
):
    me = make_db_user(db_session, Role.STUDENT, email="me@example.test", tenant_id=1)
    seed_notification(db_session, user_id=me.id, title="hello", message="world")
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=me.id, tenant_id=1)
    )

    response = client.get("/notifications")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item.keys()) == {"id", "title", "message", "read_at", "created_at"}
    assert item["title"] == "hello"
    assert item["message"] == "world"
    assert item["read_at"] is None