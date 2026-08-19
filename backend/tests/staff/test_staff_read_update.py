"""GET/PATCH /staff endpoint tests (E12, Journey J5, issue #120)."""

from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user
from tests.staff.helpers import make_staff_payload


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


def test_owner_can_list_staff_across_branches(client, db_session, override_authenticated_user):
    branch_one = seed_branch(db_session, tenant_id=1, name="Branch One", city="Mumbai")
    branch_two = seed_branch(db_session, tenant_id=1, name="Branch Two", city="Delhi")
    staff_one = _seed_staff_user(
        db_session,
        email="staff.b1@example.test",
        branch_id=branch_one.id,
    )
    staff_two = _seed_staff_user(
        db_session,
        email="staff.b2@example.test",
        role=Role.RECEPTIONIST,
        branch_id=branch_two.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.get("/staff")

    assert response.status_code == 200
    staff_ids = {item["id"] for item in response.json()}
    assert staff_ids == {staff_one, staff_two}


def test_branch_manager_list_staff_limited_to_own_branch(
    client, db_session, override_authenticated_user
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_branch = seed_branch(db_session, tenant_id=1, name="Other Branch", city="Delhi")
    own_staff = _seed_staff_user(
        db_session,
        email="own.staff@example.test",
        branch_id=own_branch.id,
    )
    _seed_staff_user(
        db_session,
        email="other.staff@example.test",
        branch_id=other_branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=own_branch.id,
        )
    )

    response = client.get("/staff")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [own_staff]


def test_owner_can_get_staff_by_id(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="detail@example.test",
        role=Role.DOCUMENT_VERIFIER,
        branch_id=branch.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.get(f"/staff/{staff_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == staff_id
    assert body["email"] == "detail@example.test"
    assert body["role"] == Role.DOCUMENT_VERIFIER.value
    assert body["branch_id"] == branch.id


def test_owner_can_update_staff_role_and_branch(client, db_session, override_authenticated_user):
    branch_one = seed_branch(db_session, tenant_id=1, name="Branch One", city="Mumbai")
    branch_two = seed_branch(db_session, tenant_id=1, name="Branch Two", city="Delhi")
    staff_id = _seed_staff_user(
        db_session,
        email="editable@example.test",
        role=Role.COUNSELOR,
        branch_id=branch_one.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.patch(
        f"/staff/{staff_id}",
        json={"role": Role.RECEPTIONIST.value, "branch_id": branch_two.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == Role.RECEPTIONIST.value
    assert body["branch_id"] == branch_two.id


def test_branch_manager_can_update_staff_in_own_branch(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Chennai")
    staff_id = _seed_staff_user(
        db_session,
        email="own.branch.staff@example.test",
        role=Role.COUNSELOR,
        branch_id=branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.patch(
        f"/staff/{staff_id}",
        json={"role": Role.VISA_PROCESSOR.value},
    )

    assert response.status_code == 200
    assert response.json()["role"] == Role.VISA_PROCESSOR.value
    assert response.json()["branch_id"] == branch.id


def test_branch_manager_cannot_update_staff_in_other_branch(
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

    response = client.patch(
        f"/staff/{other_staff}",
        json={"role": Role.RECEPTIONIST.value},
    )

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


def test_branch_manager_cannot_move_staff_to_other_branch(
    client, db_session, override_authenticated_user
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_branch = seed_branch(db_session, tenant_id=1, name="Other Branch", city="Delhi")
    staff_id = _seed_staff_user(
        db_session,
        email="move.attempt@example.test",
        branch_id=own_branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=own_branch.id,
        )
    )

    response = client.patch(
        f"/staff/{staff_id}",
        json={"branch_id": other_branch.id},
    )

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


def test_unauthenticated_get_staff_rejected(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(db_session, branch_id=branch.id)

    response = client.get(f"/staff/{staff_id}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_unauthenticated_update_staff_rejected(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(db_session, branch_id=branch.id)

    response = client.patch(f"/staff/{staff_id}", json={"role": Role.RECEPTIONIST.value})

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_update_staff_rejects_non_manager_roles(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(db_session, branch_id=branch.id)
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, tenant_id=1, branch_id=branch.id))

    response = client.patch(f"/staff/{staff_id}", json={"role": Role.RECEPTIONIST.value})

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_get_staff_returns_404_for_unknown_id(client, db_session, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.get("/staff/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Staff member not found"


def test_update_staff_rejects_empty_payload(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(db_session, branch_id=branch.id)
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.patch(f"/staff/{staff_id}", json={})

    assert response.status_code == 422
    assert response.json()["detail"] == "At least one field must be provided"


def test_update_staff_with_real_jwt(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)
    staff_id = _seed_staff_user(
        db_session,
        email="jwt.staff@example.test",
        role=Role.COUNSELOR,
        branch_id=branch.id,
    )
    password = "owner-password"
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@staff-edit.test",
        password=password,
        tenant_id=1,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "owner@staff-edit.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.patch(
        f"/staff/{staff_id}",
        headers=make_auth_headers(access_token),
        json={"role": Role.RECEPTIONIST.value},
    )

    assert response.status_code == 200
    assert response.json()["role"] == Role.RECEPTIONIST.value


def test_create_staff_still_works_after_read_update_routes(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email="still.creates@example.test",
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 201
    assert response.json()["email"] == "still.creates@example.test"
