"""End-to-end branch management flow tests (E11, Journey J4, issue #118)."""

from app.rbac.roles import Role
from tests.branches.helpers import make_branch_payload
from tests.factories.users import make_authenticated_user


def test_owner_branch_create_list_and_update_flow(client, override_authenticated_user):
    """Consultancy owner creates a branch, lists it, and updates its details."""
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    create_response = client.post(
        "/branches",
        json=make_branch_payload(name="Flow Branch", city="Chennai"),
    )
    assert create_response.status_code == 201
    created = create_response.json()
    branch_id = created["id"]

    list_response = client.get("/branches")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == branch_id
    assert listed[0]["name"] == "Flow Branch"
    assert listed[0]["city"] == "Chennai"

    update_response = client.patch(
        f"/branches/{branch_id}",
        json={"name": "Flow Branch Updated", "city": "Coimbatore"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Flow Branch Updated"
    assert updated["city"] == "Coimbatore"

    list_after_update = client.get("/branches")
    assert list_after_update.status_code == 200
    assert list_after_update.json()[0]["name"] == "Flow Branch Updated"
