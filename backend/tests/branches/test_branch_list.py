"""GET /branches endpoint tests (E11, Journey J4, issue #115)."""

from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


def test_list_branches_returns_owner_tenant_only(client, db_session, override_authenticated_user):
    seed_branch(db_session, tenant_id=1, name="Mumbai HQ", city="Mumbai")
    seed_branch(db_session, tenant_id=1, name="Delhi Center", city="Delhi")
    seed_branch(db_session, tenant_id=2, name="Other Tenant Branch", city="Bangalore")

    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.get("/branches")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {branch["name"] for branch in body} == {"Mumbai HQ", "Delhi Center"}
    assert all(branch["tenant_id"] == 1 for branch in body)


def test_list_branches_empty_for_new_tenant(client, override_authenticated_user):
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=99)
    )

    response = client.get("/branches")

    assert response.status_code == 200
    assert response.json() == []


def test_list_branches_rejects_unauthenticated_request(client):
    response = client.get("/branches")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_list_branches_rejects_non_owner(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.BRANCH_MANAGER))

    response = client.get("/branches")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
