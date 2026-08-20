"""Signup validation tests for POST /auth/register-student (E16, Journey J9, issue #140)."""

<<<<<<< HEAD
from datetime import date, timedelta
=======
>>>>>>> origin/main

from app.auth import verify_access_token, verify_refresh_token
from app.auth.password import verify_password
from app.models.user import User
from app.rbac.roles import Role
from tests.auth.register_student_helpers import (
    VALID_PASSWORD,
    create_tenant,
    make_register_student_payload,
)
from tests.branches.helpers import seed_branch
from tests.master_data.helpers import seed_master_data_chain

<<<<<<< HEAD
=======
VALID_PASSWORD = "StudentPass1!"


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def make_register_student_payload(
    *,
    tenant_slug: str = "apex",
    branch_id: int = 1,
    email: str = "new.student@example.test",
    password: str = VALID_PASSWORD,
    name: str = "Rahul Kumar",
    phone: str = "+91-9876543210",
    date_of_birth: str = "2000-05-15",
    target_country_id: int | None = None,
    target_university_id: int | None = None,
    target_program_id: int | None = None,
) -> dict:
    payload = {
        "tenant_slug": tenant_slug,
        "branch_id": branch_id,
        "email": email,
        "password": password,
        "name": name,
        "phone": phone,
        "date_of_birth": date_of_birth,
    }
    if target_country_id is not None:
        payload["target_country_id"] = target_country_id
    if target_university_id is not None:
        payload["target_university_id"] = target_university_id
    if target_program_id is not None:
        payload["target_program_id"] = target_program_id
    return payload

>>>>>>> origin/main

def test_register_student_success(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    country, university, program = seed_master_data_chain(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            target_country_id=country.id,
            target_university_id=university.id,
            target_program_id=program.id,
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.student@example.test"
    assert body["role"] == Role.STUDENT.value
    assert body["tenant_id"] == tenant.id
    assert body["branch_id"] == branch.id
    assert body["name"] == "Rahul Kumar"
    assert body["phone"] == "+91-9876543210"
    assert body["date_of_birth"] == "2000-05-15"
    assert body["target_country_id"] == country.id
    assert body["target_university_id"] == university.id
    assert body["target_program_id"] == program.id
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert isinstance(body["refresh_token"], str)
    assert "id" in body
    assert "created_at" in body

    verified_access = verify_access_token(body["access_token"])
    assert verified_access.id == body["id"]
    assert verified_access.role == Role.STUDENT
    assert verified_access.tenant_id == tenant.id
    assert verified_access.branch_id == branch.id

    verified_refresh = verify_refresh_token(body["refresh_token"])
    assert verified_refresh.id == body["id"]
    assert verified_refresh.role == Role.STUDENT


def test_register_student_persists_hashed_password(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    plain_password = VALID_PASSWORD

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="hash.student@example.test",
            password=plain_password,
        ),
    )

    assert response.status_code == 201
    user = db_session.get(User, response.json()["id"])
    assert user is not None
    assert verify_password(plain_password, user.password_hash)


def test_register_student_normalizes_email(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="  MixedCase@Example.TEST  ",
        ),
    )

    assert response.status_code == 201
    assert response.json()["email"] == "mixedcase@example.test"


def test_register_student_normalizes_tenant_slug(client, db_session):
    tenant = create_tenant(db_session, slug="apex")
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug="  APEX  ",
            branch_id=branch.id,
            email="slug.student@example.test",
        ),
    )

    assert response.status_code == 201
    assert response.json()["tenant_id"] == tenant.id


def test_register_student_strips_name_and_phone(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="strip.fields@example.test",
            name="  Rahul Kumar  ",
            phone="  +91-9876543210  ",
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Rahul Kumar"
    assert body["phone"] == "+91-9876543210"


def test_register_student_allows_optional_target_fields(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json={
            "tenant_slug": tenant.slug,
            "branch_id": branch.id,
            "email": "minimal.student@example.test",
            "password": VALID_PASSWORD,
            "name": "Minimal Student",
            "phone": "+91-9000000000",
            "date_of_birth": "1999-01-01",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["target_country_id"] is None
    assert body["target_university_id"] is None
    assert body["target_program_id"] is None


def test_register_student_can_login_after_registration(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    password = VALID_PASSWORD

    register_response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="login.after@example.test",
            password=password,
        ),
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": "login.after@example.test", "password": password},
    )

    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"


def test_register_student_rejects_unknown_tenant(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug="missing-tenant",
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


def test_register_student_rejects_unknown_branch(client, db_session):
    create_tenant(db_session)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(branch_id=9999),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Branch not found"


def test_register_student_rejects_cross_tenant_branch(client, db_session):
    tenant = create_tenant(db_session, slug="apex")
    other_tenant = create_tenant(db_session, name="Other Consultancy", slug="other")
    other_branch = seed_branch(db_session, tenant_id=other_tenant.id, name="Other Branch")

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug=tenant.slug,
            branch_id=other_branch.id,
            email="cross.tenant@example.test",
        ),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Branch not found"


def test_register_student_rejects_invalid_email(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="not-an-email",
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_invalid_tenant_slug(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug="Invalid Slug!",
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_missing_required_fields(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json={
            "tenant_slug": tenant.slug,
            "branch_id": branch.id,
            "email": "incomplete@example.test",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 422


def test_register_student_rejects_whitespace_only_name(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="blank.name@example.test",
            name="   ",
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_whitespace_only_phone(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="blank.phone@example.test",
            phone="   ",
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_weak_password(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="weak.password@example.test",
            password="password",
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_short_password(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="short.password@example.test",
            password="Ab1!",
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_whitespace_only_password(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="blank.password@example.test",
            password="   ",
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_future_date_of_birth(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="future.dob@example.test",
            date_of_birth="2099-01-01",
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_implausible_date_of_birth(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="old.dob@example.test",
            date_of_birth="1860-01-01",
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_student_under_minimum_age(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    too_young_dob = (date.today() - timedelta(days=365 * 9)).isoformat()

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="young.student@example.test",
            date_of_birth=too_young_dob,
        ),
    )

    assert response.status_code == 422


def test_register_student_rejects_invalid_target_country_id(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="bad.country@example.test",
            target_country_id=0,
        ),
    )

    assert response.status_code == 422
