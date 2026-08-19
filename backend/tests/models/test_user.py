from datetime import datetime, timezone

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


def test_user_email_is_unique(db_session):
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
