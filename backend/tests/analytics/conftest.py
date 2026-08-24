"""Shared fixtures for analytics tests."""

from datetime import datetime, timezone

import pytest

from app.auth import create_access_token
from app.rbac.roles import Role
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user


@pytest.fixture
def branch_manager(db_session):
    """Create a branch manager user and return the ORM object."""
    return make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="branch.manager@example.test",
        password="manager-password",
        tenant_id=1,
        branch_id=1,
    )


@pytest.fixture
def branch_manager_auth_headers(branch_manager):
    """Auth headers for the branch manager fixture."""
    manager_auth = make_authenticated_user(
        Role.BRANCH_MANAGER,
        user_id=branch_manager.id,
        tenant_id=branch_manager.tenant_id,
        branch_id=branch_manager.branch_id,
    )
    token = create_access_token(manager_auth)
    return make_auth_headers(token)


@pytest.fixture
def consultancy_owner(db_session):
    """Create a consultancy owner user and return the ORM object."""
    return make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@example.test",
        password="owner-password",
        tenant_id=1,
    )


@pytest.fixture
def owner_auth_headers(consultancy_owner):
    """Auth headers for the consultancy owner fixture."""
    owner_auth = make_authenticated_user(
        Role.CONSULTANCY_OWNER,
        user_id=consultancy_owner.id,
        tenant_id=consultancy_owner.tenant_id,
    )
    token = create_access_token(owner_auth)
    return make_auth_headers(token)


@pytest.fixture
def other_branch_manager(db_session):
    """Create a second branch manager in the same tenant for scoping tests."""
    return make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="other.branch.manager@example.test",
        password="other-manager-password",
        tenant_id=1,
        branch_id=2,  # Different branch
    )


@pytest.fixture
def make_user(db_session):
    """Factory to create test users with optional created_at timestamp."""
    def _make_user(
        role: Role,
        tenant_id: int = 1,
        branch_id: int = 1,
        created_at: datetime | None = None,
    ):
        from app.models.user import User
        from app.auth.password import hash_password
        from tests.factories.ids import next_test_id

        now = datetime.now(timezone.utc)
        user = User(
            email=f"{role.value}-{next_test_id()}@example.test",
            password_hash=hash_password("test-password"),
            role=role,
            tenant_id=tenant_id,
            branch_id=branch_id,
            is_active=True,
            created_at=created_at or now,
            updated_at=now,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make_user
