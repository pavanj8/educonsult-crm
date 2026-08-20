"""Tenant scoping tests for branch CRUD endpoints (E11, Journey J4, issue #118).

Proves branches are isolated per tenant: create assigns the caller's tenant_id,
list returns only the caller's tenant, and update never leaks or mutates another
tenant's branches (Requirements §1 multi-tenancy; ADR-0004).
"""

from app.rbac.roles import Role
from tests.branches.helpers import make_branch_payload, seed_branch
from tests.factories.users import make_authenticated_user


def test_create_branch_always_uses_callers_tenant_id(client, override_authenticated_user):
    """Created branches inherit tenant_id from the authenticated owner, not the payload."""
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=42)
    )

    response = client.post(
        "/branches",
        json=make_branch_payload(name="Tenant 42 Branch", city="Chennai"),
    )

    assert response.status_code == 201
    assert response.json()["tenant_id"] == 42


def test_two_tenants_maintain_isolated_branch_lists(
    client, db_session, override_authenticated_user
):
    """Consultancy owners of different tenants each see only their own branches."""
    seed_branch(db_session, tenant_id=1, name="T1 Branch A", city="Mumbai")
    seed_branch(db_session, tenant_id=1, name="T1 Branch B", city="Delhi")
    seed_branch(db_session, tenant_id=2, name="T2 Branch", city="Bangalore")

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )
    tenant_one = client.get("/branches")
    assert tenant_one.status_code == 200
    assert {branch["name"] for branch in tenant_one.json()} == {
        "T1 Branch A",
        "T1 Branch B",
    }
    assert all(branch["tenant_id"] == 1 for branch in tenant_one.json())

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=2)
    )
    tenant_two = client.get("/branches")
    assert tenant_two.status_code == 200
    assert {branch["name"] for branch in tenant_two.json()} == {"T2 Branch"}
    assert all(branch["tenant_id"] == 2 for branch in tenant_two.json())


def test_cross_tenant_update_returns_not_found(client, db_session, override_authenticated_user):
    """Updating another tenant's branch yields 404 so existence is not leaked."""
    other_tenant_branch = seed_branch(
        db_session,
        tenant_id=99,
        name="Secret Branch",
        city="Kolkata",
    )
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(
        f"/branches/{other_tenant_branch.id}",
        json={"name": "Stolen"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Branch not found"


def test_multi_tenant_owners_create_isolated_branches(client, override_authenticated_user):
    """Branches created by one tenant owner are invisible to another tenant owner."""
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=10)
    )
    create_tenant_10 = client.post(
        "/branches",
        json=make_branch_payload(name="T10 Office", city="Chennai"),
    )
    assert create_tenant_10.status_code == 201
    assert create_tenant_10.json()["tenant_id"] == 10

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=20)
    )
    create_tenant_20 = client.post(
        "/branches",
        json=make_branch_payload(name="T20 Office", city="Hyderabad"),
    )
    assert create_tenant_20.status_code == 201
    assert create_tenant_20.json()["tenant_id"] == 20

    list_tenant_20 = client.get("/branches")
    assert list_tenant_20.status_code == 200
    assert len(list_tenant_20.json()) == 1
    assert list_tenant_20.json()[0]["name"] == "T20 Office"

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=10)
    )
    list_tenant_10 = client.get("/branches")
    assert list_tenant_10.status_code == 200
    assert len(list_tenant_10.json()) == 1
    assert list_tenant_10.json()[0]["name"] == "T10 Office"
