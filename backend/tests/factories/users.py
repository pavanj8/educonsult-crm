from datetime import datetime, timezone
from typing import Any

from app.auth.password import hash_password
from app.models.user import User
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser

from tests.factories.ids import next_test_id

_AUTO = object()

# Roles restricted to a single branch within their tenant (ADR-0004, branch_scope.py).
_BRANCH_SCOPED_ROLES = frozenset(
    {
        Role.BRANCH_MANAGER,
        Role.COUNSELOR,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
        Role.STUDENT,
    }
)


def make_authenticated_user(
    role: Role,
    *,
    user_id: int | None = None,
    tenant_id: int | None | Any = _AUTO,
    branch_id: int | None | Any = _AUTO,
) -> AuthenticatedUser:
    """Build an ``AuthenticatedUser`` with role-appropriate tenant/branch defaults.

    Pass ``tenant_id=None`` or ``branch_id=None`` explicitly to override defaults
    (e.g. when testing missing-scope error paths).
    """
    resolved_user_id = next_test_id() if user_id is None else user_id

    resolved_tenant_id = tenant_id
    if tenant_id is _AUTO:
        resolved_tenant_id = None if role == Role.SUPER_ADMIN else 1

    resolved_branch_id = branch_id
    if branch_id is _AUTO:
        if role in (Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER):
            resolved_branch_id = None
        elif role in _BRANCH_SCOPED_ROLES:
            resolved_branch_id = 1
        else:
            resolved_branch_id = None

    return AuthenticatedUser(
        id=resolved_user_id,
        role=role,
        tenant_id=resolved_tenant_id,
        branch_id=resolved_branch_id,
    )


def make_db_user(
    db_session,
    role: Role,
    *,
    email: str | None = None,
    password: str = "test-password",
    tenant_id: int | None | Any = _AUTO,
    branch_id: int | None | Any = _AUTO,
) -> User:
    """Persist a ``User`` row with a bcrypt password hash for integration tests."""
    auth_user = make_authenticated_user(
        role,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )
    now = datetime.now(timezone.utc)
    user = User(
        email=email or f"{role.value}-{next_test_id()}@example.test",
        password_hash=hash_password(password),
        role=auth_user.role,
        tenant_id=auth_user.tenant_id,
        branch_id=auth_user.branch_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
