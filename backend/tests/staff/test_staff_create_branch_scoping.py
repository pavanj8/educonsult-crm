"""Staff creation branch-scoping tests (E12, Journey J5, issue #121).

Proves POST /staff respects branch assignment rules from Requirements §3:
- Consultancy Owner may create staff in any branch within their tenant.
- Branch Manager may create staff only in their own branch.
"""

import pytest

from app.models.user import User
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user
from tests.staff.helpers import make_staff_payload

_BRANCH_MANAGER_CREATABLE_ROLES = [
    Role.COUNSELOR,
    Role.DOCUMENT_VERIFIER,
    Role.VISA_PROCESSOR,
    Role.RECEPTIONIST,
]

_OWNER_CREATABLE_ROLES = _BRANCH_MANAGER_CREATABLE_ROLES + [Role.BRANCH_MANAGER]


def test_owner_can_create_staff_in_any_branch(client, db_session, override_authenticated_user):
    branch_one = seed_branch(db_session, tenant_id=1, name="Branch One", city="Mumbai")
    branch_two = seed_branch(db_session, tenant_id=1, name="Branch Two", city="Delhi")
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response_one = client.post(
        "/staff",
        json=make_staff_payload(
            email="counselor.b1@example.test",
            branch_id=branch_one.id,
        ),
    )
    response_two = client.post(
        "/staff",
        json=make_staff_payload(
            email="counselor.b2@example.test",
            role=Role.RECEPTIONIST,
            branch_id=branch_two.id,
        ),
    )

    assert response_one.status_code == 201
    assert response_one.json()["branch_id"] == branch_one.id
    assert response_one.json()["tenant_id"] == 1
    assert response_one.json()["role"] == Role.COUNSELOR.value

    assert response_two.status_code == 201
    assert response_two.json()["branch_id"] == branch_two.id
    assert response_two.json()["role"] == Role.RECEPTIONIST.value


@pytest.mark.parametrize("role", _OWNER_CREATABLE_ROLES)
def test_owner_can_create_each_staff_role_in_any_branch(
    client, db_session, override_authenticated_user, role: Role
):
    branch = seed_branch(
        db_session,
        tenant_id=1,
        name=f"Branch for {role.value}",
        city="Pune",
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email=f"owner.{role.value}@example.test",
            role=role,
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 201
    assert response.json()["role"] == role.value
    assert response.json()["branch_id"] == branch.id


def test_branch_manager_can_create_staff_in_own_branch(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Chennai")
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email="verifier@example.test",
            role=Role.DOCUMENT_VERIFIER,
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 201
    assert response.json()["branch_id"] == branch.id
    assert response.json()["role"] == Role.DOCUMENT_VERIFIER.value


@pytest.mark.parametrize("role", _BRANCH_MANAGER_CREATABLE_ROLES)
def test_branch_manager_can_create_each_operational_role_in_own_branch(
    client, db_session, override_authenticated_user, role: Role
):
    branch = seed_branch(
        db_session,
        tenant_id=1,
        name=f"Own Branch {role.value}",
        city="Chennai",
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email=f"manager.{role.value}@example.test",
            role=role,
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 201
    assert response.json()["branch_id"] == branch.id
    assert response.json()["role"] == role.value


def test_branch_manager_cannot_create_staff_in_other_branch(
    client, db_session, override_authenticated_user
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_branch = seed_branch(db_session, tenant_id=1, name="Other Branch", city="Delhi")
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=own_branch.id,
        )
    )

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email="counselor.other@example.test",
            branch_id=other_branch.id,
        ),
    )

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


@pytest.mark.parametrize("role", _BRANCH_MANAGER_CREATABLE_ROLES)
def test_branch_manager_cannot_create_staff_in_other_branch_for_any_role(
    client, db_session, override_authenticated_user, role: Role
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_branch = seed_branch(
        db_session,
        tenant_id=1,
        name=f"Other Branch {role.value}",
        city="Delhi",
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=own_branch.id,
        )
    )

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email=f"denied.{role.value}@example.test",
            role=role,
            branch_id=other_branch.id,
        ),
    )

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


def test_branch_manager_cannot_create_branch_manager(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email="peer.manager@example.test",
            role=Role.BRANCH_MANAGER,
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


def test_owner_cross_branch_create_with_real_jwt(client, db_session):
    branch_one = seed_branch(db_session, tenant_id=1, name="JWT Branch One", city="Bangalore")
    branch_two = seed_branch(db_session, tenant_id=1, name="JWT Branch Two", city="Hyderabad")
    password = "owner-password"
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner.crossbranch@staff.test",
        password=password,
        tenant_id=1,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "owner.crossbranch@staff.test", "password": password},
    )
    headers = make_auth_headers(login_response.json()["access_token"])

    response_one = client.post(
        "/staff",
        headers=headers,
        json=make_staff_payload(
            email="jwt.b1@example.test",
            branch_id=branch_one.id,
        ),
    )
    response_two = client.post(
        "/staff",
        headers=headers,
        json=make_staff_payload(
            email="jwt.b2@example.test",
            role=Role.VISA_PROCESSOR,
            branch_id=branch_two.id,
        ),
    )

    assert response_one.status_code == 201
    assert response_one.json()["branch_id"] == branch_one.id
    assert response_two.status_code == 201
    assert response_two.json()["branch_id"] == branch_two.id


def test_branch_manager_jwt_limited_to_own_branch(client, db_session):
    own_branch = seed_branch(db_session, tenant_id=1, name="Manager Branch", city="Chennai")
    other_branch = seed_branch(db_session, tenant_id=1, name="Remote Branch", city="Kolkata")
    password = "manager-password"
    make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="manager.branch@staff.test",
        password=password,
        tenant_id=1,
        branch_id=own_branch.id,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "manager.branch@staff.test", "password": password},
    )
    headers = make_auth_headers(login_response.json()["access_token"])

    allowed = client.post(
        "/staff",
        headers=headers,
        json=make_staff_payload(
            email="jwt.own.branch@example.test",
            role=Role.RECEPTIONIST,
            branch_id=own_branch.id,
        ),
    )
    denied = client.post(
        "/staff",
        headers=headers,
        json=make_staff_payload(
            email="jwt.other.branch@example.test",
            branch_id=other_branch.id,
        ),
    )

    assert allowed.status_code == 201
    assert allowed.json()["branch_id"] == own_branch.id
    created = db_session.get(User, allowed.json()["id"])
    assert created is not None
    assert created.branch_id == own_branch.id

    assert denied.status_code == 403
    assert "cannot act on user" in denied.json()["detail"]
