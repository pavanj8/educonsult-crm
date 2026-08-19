"""POST /staff/{id}/deactivate and /reactivate endpoint tests (E13, Journey J6, issue #122)."""

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
    is_active: bool = True,
) -> int:
    user = make_db_user(
        db_session,
        role,
        email=email,
        tenant_id=tenant_id,
        branch_id=branch_id,
        is_active=is_active,
    )
    return user.id


def test_owner_can_deactivate_staff(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="deactivate.me@example.test",
        branch_id=branch.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(f"/staff/{staff_id}/deactivate")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == staff_id
    assert body["is_active"] is False


def test_owner_can_reactivate_staff(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="reactivate.me@example.test",
        branch_id=branch.id,
        is_active=False,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(f"/staff/{staff_id}/reactivate")

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_branch_manager_can_deactivate_staff_in_own_branch(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    staff_id = _seed_staff_user(
        db_session,
        email="own.branch.staff@example.test",
        branch_id=branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.post(f"/staff/{staff_id}/deactivate")

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_branch_manager_cannot_deactivate_staff_in_other_branch(
    client, db_session, override_authenticated_user
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_branch = seed_branch(db_session, tenant_id=1, name="Other Branch", city="Delhi")
    other_staff = _seed_staff_user(
        db_session,
        email="other.branch.staff@example.test",
        branch_id=other_branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=own_branch.id,
        )
    )

    response = client.post(f"/staff/{other_staff}/deactivate")

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


def test_counselor_cannot_deactivate_staff(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(db_session, branch_id=branch.id)
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, tenant_id=1, branch_id=branch.id))

    response = client.post(f"/staff/{staff_id}/deactivate")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_deactivate_rejects_already_inactive_staff(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="already.inactive@example.test",
        branch_id=branch.id,
        is_active=False,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(f"/staff/{staff_id}/deactivate")

    assert response.status_code == 409
    assert response.json()["detail"] == "Staff member is already inactive"


def test_reactivate_rejects_already_active_staff(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="already.active@example.test",
        branch_id=branch.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(f"/staff/{staff_id}/reactivate")

    assert response.status_code == 409
    assert response.json()["detail"] == "Staff member is already active"


def test_cannot_change_own_active_status(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="self.manager@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            user_id=manager.id,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.post(f"/staff/{manager.id}/deactivate")

    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot change your own active status"


def test_deactivated_staff_cannot_login(client, db_session):
    password = "staff-password"
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="inactive.staff@example.test",
        password=password,
        tenant_id=1,
        branch_id=1,
        is_active=False,
    )

    response = client.post(
        "/auth/login",
        json={"email": "inactive.staff@example.test", "password": password},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is deactivated"


def test_deactivated_staff_cannot_refresh_token(client, db_session):
    password = "staff-password"
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="inactive.refresh@example.test",
        password=password,
        tenant_id=1,
        branch_id=1,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "inactive.refresh@example.test", "password": password},
    )
    refresh_token = login_response.json()["refresh_token"]

    user.is_active = False
    db_session.commit()

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is deactivated"


def test_staff_list_includes_is_active(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    active_staff = _seed_staff_user(
        db_session,
        email="active.staff@example.test",
        branch_id=branch.id,
    )
    inactive_staff = _seed_staff_user(
        db_session,
        email="inactive.staff@example.test",
        branch_id=branch.id,
        is_active=False,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.get("/staff")

    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()}
    assert by_id[active_staff]["is_active"] is True
    assert by_id[inactive_staff]["is_active"] is False


def test_deactivate_staff_with_real_jwt(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="jwt.deactivate@example.test",
        branch_id=branch.id,
    )
    password = "owner-password"
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@deactivate.test",
        password=password,
        tenant_id=1,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "owner@deactivate.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.post(
        f"/staff/{staff_id}/deactivate",
        headers=make_auth_headers(access_token),
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_unauthenticated_deactivate_rejected(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(db_session, branch_id=branch.id)

    response = client.post(f"/staff/{staff_id}/deactivate")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
