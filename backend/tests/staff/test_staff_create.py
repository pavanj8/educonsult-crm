"""POST /staff endpoint tests (E12, Journey J5, issue #119).

General staff creation behaviour (validation, auth, persistence). Branch-scoping
rules for owner vs branch manager are covered in test_staff_create_branch_scoping.py
(issue #121).
"""

from app.auth import create_access_token
from app.auth.password import verify_password
from app.models.user import User
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user
from tests.staff.helpers import make_staff_payload


def test_create_staff_success_with_real_jwt(client, db_session):
    branch = seed_branch(db_session, tenant_id=1, name="JWT Branch", city="Bangalore")
    password = "owner-password"
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@staff.test",
        password=password,
        tenant_id=1,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "owner@staff.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.post(
        "/staff",
        headers=make_auth_headers(access_token),
        json=make_staff_payload(
            email="jwt.counselor@example.test",
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jwt.counselor@example.test"
    assert body["branch_id"] == branch.id


def test_create_staff_persists_hashed_password(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))
    plain_password = "staff-plain-password"

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email="hash.test@example.test",
            password=plain_password,
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 201
    user = db_session.get(User, response.json()["id"])
    assert user is not None
    assert verify_password(plain_password, user.password_hash)


def test_create_staff_normalizes_email(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email="  MixedCase@Example.TEST  ",
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 201
    assert response.json()["email"] == "mixedcase@example.test"


def test_create_staff_rejects_unauthenticated_request(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)

    response = client.post(
        "/staff",
        json=make_staff_payload(branch_id=branch.id),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_create_staff_rejects_non_manager_roles(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, tenant_id=1, branch_id=branch.id))

    response = client.post(
        "/staff",
        json=make_staff_payload(branch_id=branch.id),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_create_staff_rejects_invalid_staff_role(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email="student@example.test",
            role=Role.STUDENT,
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid staff role"


def test_create_staff_rejects_unknown_branch(client, db_session, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(
        "/staff",
        json=make_staff_payload(branch_id=9999),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Branch not found"


def test_create_staff_rejects_cross_tenant_branch(client, db_session, override_authenticated_user):
    other_tenant_branch = seed_branch(db_session, tenant_id=99, name="Other Tenant", city="Kolkata")
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(
        "/staff",
        json=make_staff_payload(
            email="cross.tenant@example.test",
            branch_id=other_tenant_branch.id,
        ),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Branch not found"


def test_create_staff_rejects_duplicate_email(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))
    payload = make_staff_payload(
        email="duplicate@example.test",
        branch_id=branch.id,
    )

    first = client.post("/staff", json=payload)
    second = client.post("/staff", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "A user with this email already exists"


def test_create_staff_rejects_invalid_access_token(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)

    response = client.post(
        "/staff",
        headers=make_auth_headers("not-a-valid-jwt"),
        json=make_staff_payload(branch_id=branch.id),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_create_staff_rejects_counselor_jwt(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=1,
        branch_id=branch.id,
    )
    token = create_access_token(make_authenticated_user(Role.COUNSELOR, user_id=user.id, branch_id=branch.id))

    response = client.post(
        "/staff",
        headers=make_auth_headers(token),
        json=make_staff_payload(branch_id=branch.id),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
