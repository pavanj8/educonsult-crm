"""POST /students receptionist-scope tests (E17, issue #141)."""

from app.auth.password import verify_password
from app.models.user import User
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


def student_payload(branch_id: int, **overrides):
    payload = {
        "email": "walkin@example.test",
        "password": "Walkin-password-123",
        "name": "Walk In Student",
        "phone": "+91 9876543210",
        "date_of_birth": "2000-01-01",
        "branch_id": branch_id,
    }
    payload.update(overrides)
    return payload


def test_receptionist_creates_student_record(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.RECEPTIONIST, user_id=11, tenant_id=1, branch_id=branch.id)
    )

    response = client.post("/students", json=student_payload(branch.id))

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "student"
    assert body["tenant_id"] == 1
    assert body["branch_id"] == branch.id
    student = db_session.get(User, body["id"])
    assert student is not None
    assert verify_password("Walkin-password-123", student.password_hash)


def test_owner_creates_student_record(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post("/students", json=student_payload(branch.id))

    assert response.status_code == 201
    assert response.json()["branch_id"] == branch.id


def test_receptionist_cannot_create_for_other_branch(client, db_session, override_authenticated_user):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own")
    other_branch = seed_branch(db_session, tenant_id=1, name="Other")
    override_authenticated_user(
        make_authenticated_user(Role.RECEPTIONIST, tenant_id=1, branch_id=own_branch.id)
    )

    response = client.post("/students", json=student_payload(other_branch.id))

    assert response.status_code == 403


def test_counselor_cannot_create_student_record(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, tenant_id=1, branch_id=branch.id)
    )

    response = client.post("/students", json=student_payload(branch.id))

    assert response.status_code == 403


def test_duplicate_email_is_rejected(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.RECEPTIONIST, tenant_id=1, branch_id=branch.id)
    )
    payload = student_payload(branch.id)

    assert client.post("/students", json=payload).status_code == 201
    response = client.post("/students", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "A user with this email already exists"


def test_invalid_student_payload_is_rejected(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.RECEPTIONIST, tenant_id=1, branch_id=branch.id)
    )

    response = client.post("/students", json=student_payload(branch.id, date_of_birth="2030-01-01"))

    assert response.status_code == 422
