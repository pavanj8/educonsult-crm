"""Duplicate-email handling tests for POST /auth/register-student (E16, issue #140).

Per docs/requirements.md §1 the system is multi-tenant and "every table carries
a tenant_id"; the same identifier in different tenants is independent. Email
uniqueness is therefore scoped per tenant (backend/app/auth/email_uniqueness.py
+ the composite UNIQUE(tenant_id, email) DB constraint added in migration
``i2j3k4l5m6n7``).
"""

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


def test_register_student_allows_email_reuse_across_tenants(client, db_session):
    """The same email may legitimately be registered in two different consultancies.

    Multi-tenant contract from docs/requirements.md §1 — every table carries a
    ``tenant_id``; the same identifier in different tenants is independent.
    """
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
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["tenant_id"] == tenant_a.id
    assert second.json()["tenant_id"] == tenant_b.id
    assert first.json()["email"] == "shared@example.test"
    assert second.json()["email"] == "shared@example.test"
