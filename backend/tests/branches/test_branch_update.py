"""PATCH /branches/{id} endpoint tests (E11, Journey J4, issue #115)."""

from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


def test_update_branch_success(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1, name="Mumbai HQ", city="Mumbai")
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.patch(
        f"/branches/{branch.id}",
        json={"name": "Mumbai Headquarters", "city": "Mumbai"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == branch.id
    assert body["name"] == "Mumbai Headquarters"
    assert body["city"] == "Mumbai"
    assert body["tenant_id"] == 1


def test_update_branch_partial_fields(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1, name="Delhi Center", city="Delhi")
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.patch(
        f"/branches/{branch.id}",
        json={"city": "New Delhi"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Delhi Center"
    assert body["city"] == "New Delhi"


def test_update_branch_rejects_cross_tenant_access(
    client, db_session, override_authenticated_user
):
    other_tenant_branch = seed_branch(
        db_session,
        tenant_id=2,
        name="Bangalore Office",
        city="Bangalore",
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.patch(
        f"/branches/{other_tenant_branch.id}",
        json={"name": "Hijacked"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Branch not found"


def test_update_branch_rejects_missing_branch(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.patch("/branches/9999", json={"name": "Missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Branch not found"


def test_update_branch_rejects_empty_payload(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.patch(f"/branches/{branch.id}", json={})

    assert response.status_code == 422


def test_update_branch_rejects_unauthenticated_request(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)

    response = client.patch(f"/branches/{branch.id}", json={"name": "Updated"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_update_branch_rejects_non_owner(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR))

    response = client.patch(f"/branches/{branch.id}", json={"name": "Updated"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
