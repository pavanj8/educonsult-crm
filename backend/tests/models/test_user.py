from datetime import date, datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.rbac.roles import Role

def test_user_model_has_required_columns():
    column_names = {column.key for column in inspect(User).columns}
    assert column_names == {
        "id",
        "email",
        "password_hash",
        "role",
        "tenant_id",
        "branch_id",
        "name",
        "phone",
        "date_of_birth",
        "target_country_id",
        "target_university_id",
        "target_program_id",
        "is_active",
        "created_at",
        "updated_at",
    }


@pytest.mark.parametrize(
    ("role", "tenant_id", "branch_id"),
    [
        (Role.SUPER_ADMIN, None, None),
        (Role.CONSULTANCY_OWNER, 1, None),
        (Role.COUNSELOR, 1, 1),
        (Role.STUDENT, 1, 1),
    ],
)
def test_user_persists_role_scoped_rows(
    db_session,
    role: Role,
    tenant_id: int | None,
    branch_id: int | None,
):
    now = datetime.now(timezone.utc)
    user = User(
        email=f"{role.value}@example.test",
        password_hash="hashed-secret",
        role=role,
        tenant_id=tenant_id,
        branch_id=branch_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == f"{role.value}@example.test"
    assert user.password_hash == "hashed-secret"
    assert user.role == role
    assert user.tenant_id == tenant_id
    assert user.branch_id == branch_id
    assert user.is_active is True


def test_user_email_is_unique_within_tenant(db_session):
    """Email uniqueness is scoped per tenant (docs/requirements.md §1).

    A second row with the same email in the same tenant must violate the
    composite UNIQUE(tenant_id, email) constraint, but the same email in a
    different tenant is independent and therefore allowed.
    """
    now = datetime.now(timezone.utc)
    first = User(
        email="duplicate@example.test",
        password_hash="hash-one",
        role=Role.COUNSELOR,
        tenant_id=1,
        branch_id=1,
        created_at=now,
        updated_at=now,
    )
    second = User(
        email="duplicate@example.test",
        password_hash="hash-two",
        role=Role.RECEPTIONIST,
        tenant_id=1,
        branch_id=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(first)
    db_session.commit()
    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_user_email_can_be_reused_across_tenants(db_session):
    """The same email may legitimately belong to users in different tenants."""
    now = datetime.now(timezone.utc)
    in_tenant_a = User(
        email="shared@example.test",
        password_hash="hash-a",
        role=Role.STUDENT,
        tenant_id=1,
        branch_id=1,
        created_at=now,
        updated_at=now,
    )
    in_tenant_b = User(
        email="shared@example.test",
        password_hash="hash-b",
        role=Role.STUDENT,
        tenant_id=2,
        branch_id=2,
        created_at=now,
        updated_at=now,
    )
    db_session.add(in_tenant_a)
    db_session.add(in_tenant_b)
    db_session.commit()

    db_session.refresh(in_tenant_a)
    db_session.refresh(in_tenant_b)
    assert in_tenant_a.id != in_tenant_b.id
    assert in_tenant_a.tenant_id == 1
    assert in_tenant_b.tenant_id == 2
    assert in_tenant_a.email == in_tenant_b.email == "shared@example.test"


def test_user_role_persists_snake_case_value(db_session):
    from sqlalchemy import select

    now = datetime.now(timezone.utc)
    user = User(
        email="role-value@example.test",
        password_hash="hash",
        role=Role.DOCUMENT_VERIFIER,
        tenant_id=1,
        branch_id=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()

    stored_role = db_session.execute(
        select(User.__table__.c.role).where(User.__table__.c.email == "role-value@example.test")
    ).scalar_one()
    assert stored_role == Role.DOCUMENT_VERIFIER.value


def test_student_profile_fields_persist(db_session):
    now = datetime.now(timezone.utc)
    dob = date(2000, 5, 15)
    user = User(
        email="student-profile@example.test",
        password_hash="hashed-secret",
        role=Role.STUDENT,
        tenant_id=1,
        branch_id=1,
        name="Rahul Kumar",
        phone="+91-9876543210",
        date_of_birth=dob,
        target_country_id=10,
        target_university_id=20,
        target_program_id=30,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.name == "Rahul Kumar"
    assert user.phone == "+91-9876543210"
    assert user.date_of_birth == dob
    assert user.target_country_id == 10
    assert user.target_university_id == 20
    assert user.target_program_id == 30


def test_non_student_user_profile_fields_default_null(db_session):
    now = datetime.now(timezone.utc)
    user = User(
        email="counselor-no-profile@example.test",
        password_hash="hashed-secret",
        role=Role.COUNSELOR,
        tenant_id=1,
        branch_id=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.name is None
    assert user.phone is None
    assert user.date_of_birth is None
    assert user.target_country_id is None
    assert user.target_university_id is None
    assert user.target_program_id is None
