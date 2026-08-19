"""GET /staff list and detail endpoint tests (E13, Journey J6, issue #123).

Covers tenant- and branch-scoped staff visibility for owner and branch manager roles.
"""

from app.auth import create_access_token
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user


def _seed_staff_user(
    db_session,
    *,
    email: str = "counselor@example.test",
    role: Role = Role.COUNSELOR,
    tenant_id: int = 1,
    branch_id: int,
) -> int:
    user = make_db_user(
        db_session,
        role,
        email=email,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )
    return user.id


def test_list_staff_returns_tenant_only(client, db_session, override_authenticated_user):
    branch_one = seed_branch(db_session, tenant_id=1, name="Tenant One Branch", city="Mumbai")
    branch_two = seed_branch(db_session, tenant_id=2, name="Tenant Two Branch", city="Delhi")
    tenant_one_staff = _seed_staff_user(
        db_session,
        email="tenant1.staff@example.test",
        branch_id=branch_one.id,
    )
    _seed_staff_user(
        db_session,
        email="tenant2.staff@example.test",
        tenant_id=2,
        branch_id=branch_two.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.get("/staff")

    assert response.status_code == 200
    staff_ids = {item["id"] for item in response.json()}
    assert staff_ids == {tenant_one_staff}
    assert all(item["tenant_id"] == 1 for item in response.json())


def test_list_staff_empty_for_tenant_with_no_staff(client, override_authenticated_user):
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=99)
    )

    response = client.get("/staff")

    assert response.status_code == 200
    assert response.json() == []


def test_list_staff_rejects_unauthenticated_request(client):
    response = client.get("/staff")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_list_staff_rejects_non_manager_roles(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, tenant_id=1))

    response = client.get("/staff")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_list_staff_rejects_non_manager_jwt(client, db_session):
    user = make_db_user(db_session, Role.RECEPTIONIST, tenant_id=1)
    token = create_access_token(make_authenticated_user(Role.RECEPTIONIST, user_id=user.id))

    response = client.get("/staff", headers=make_auth_headers(token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_list_staff_success_with_real_jwt(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="listed.staff@example.test",
        branch_id=branch.id,
    )
    password = "owner-password"
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@staff-list.test",
        password=password,
        tenant_id=1,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "owner@staff-list.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.get("/staff", headers=make_auth_headers(access_token))

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == staff_id


def test_list_staff_excludes_non_staff_roles(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="operational.staff@example.test",
        branch_id=branch.id,
    )
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@example.test",
        tenant_id=1,
    )
    make_db_user(
        db_session,
        Role.STUDENT,
        email="student@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.get("/staff")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [staff_id]


def test_branch_manager_can_get_staff_in_own_branch(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Chennai")
    staff_id = _seed_staff_user(
        db_session,
        email="own.detail@example.test",
        role=Role.VISA_PROCESSOR,
        branch_id=branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.get(f"/staff/{staff_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == staff_id
    assert body["email"] == "own.detail@example.test"
    assert body["role"] == Role.VISA_PROCESSOR.value
    assert body["tenant_id"] == 1
    assert body["branch_id"] == branch.id


def test_branch_manager_cannot_get_staff_in_other_branch(
    client, db_session, override_authenticated_user
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_branch = seed_branch(db_session, tenant_id=1, name="Other Branch", city="Delhi")
    other_staff = _seed_staff_user(
        db_session,
        email="other.detail@example.test",
        branch_id=other_branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=own_branch.id,
        )
    )

    response = client.get(f"/staff/{other_staff}")

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


def test_get_staff_returns_404_for_cross_tenant_staff(
    client, db_session, override_authenticated_user
):
    other_tenant_branch = seed_branch(db_session, tenant_id=2, name="Other Tenant", city="Delhi")
    other_staff = _seed_staff_user(
        db_session,
        email="cross.tenant@example.test",
        tenant_id=2,
        branch_id=other_tenant_branch.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.get(f"/staff/{other_staff}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Staff member not found"


def test_get_staff_success_with_real_jwt(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="jwt.detail@example.test",
        role=Role.COUNSELOR,
        branch_id=branch.id,
    )
    password = "owner-password"
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@staff-detail.test",
        password=password,
        tenant_id=1,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "owner@staff-detail.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.get(f"/staff/{staff_id}", headers=make_auth_headers(access_token))

    assert response.status_code == 200
    assert response.json()["email"] == "jwt.detail@example.test"


def test_get_staff_rejects_non_manager_roles(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(db_session, branch_id=branch.id)
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, tenant_id=1))

    response = client.get(f"/staff/{staff_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
