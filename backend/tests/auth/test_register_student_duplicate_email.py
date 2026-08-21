"""Duplicate-email validation for POST /auth/register-student (E16, issue #137)."""

from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_db_user

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
) -> dict:
    return {
        "tenant_slug": tenant_slug,
        "branch_id": branch_id,
        "email": email,
        "password": password,
        "name": name,
        "phone": phone,
        "date_of_birth": date_of_birth,
    }


def test_register_student_rejects_duplicate_email(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    payload = make_register_student_payload(
        branch_id=branch.id,
        email="duplicate@example.test",
    )

    first = client.post("/auth/register-student", json=payload)
    second = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="duplicate@example.test",
            name="Another Student",
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "A user with this email already exists"


def test_register_student_rejects_case_insensitive_duplicate_email(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    first = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="student@example.test",
        ),
    )
    second = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="  STUDENT@Example.TEST  ",
            name="Another Student",
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "A user with this email already exists"


def test_register_student_rejects_existing_staff_email(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="staff@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="staff@example.test",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A user with this email already exists"


def test_register_student_rejects_email_registered_in_other_tenant(client, db_session):
    tenant_a = _create_tenant(db_session, slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Other Consultancy", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id, name="Branch A")
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id, name="Branch B")

    first = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug=tenant_a.slug,
            branch_id=branch_a.id,
            email="shared@example.test",
        ),
    )
    second = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug=tenant_b.slug,
            branch_id=branch_b.id,
            email="shared@example.test",
            name="Other Tenant Student",
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "A user with this email already exists"
