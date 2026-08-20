"""Duplicate-email handling tests for POST /auth/register-student (E16, issue #140)."""

from app.rbac.roles import Role
from tests.auth.register_student_helpers import create_tenant, make_register_student_payload
from tests.branches.helpers import seed_branch
from tests.factories.users import make_db_user


def test_register_student_rejects_duplicate_email(client, db_session):
    tenant = create_tenant(db_session)
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
    tenant = create_tenant(db_session)
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
    tenant = create_tenant(db_session)
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
    tenant_a = create_tenant(db_session, slug="tenant-a")
    tenant_b = create_tenant(db_session, name="Other Consultancy", slug="tenant-b")
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
