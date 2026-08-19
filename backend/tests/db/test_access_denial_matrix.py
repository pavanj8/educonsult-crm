"""Cross-tenant and cross-branch access denial matrix (E2, ADR-0004).

Parametrized tests proving tenant-scoped and branch-scoped roles cannot
query data outside their visibility boundary when both scope filters are applied.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.branch_scope import apply_branch_scope
from app.db.tenant_scope import apply_tenant_scope
from app.models.base import Base, TenantScopedBase
from app.rbac import Role
from app.rbac.user import AuthenticatedUser


class _ScopedResource(TenantScopedBase):
    __tablename__ = "test_access_denial_resources"

    branch_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


@dataclass(frozen=True, slots=True)
class _ResourceRef:
    tenant_id: int
    branch_id: int
    name: str


TENANT_1_BRANCH_1 = _ResourceRef(tenant_id=1, branch_id=1, name="tenant-1-branch-1")
TENANT_1_BRANCH_2 = _ResourceRef(tenant_id=1, branch_id=2, name="tenant-1-branch-2")
TENANT_2_BRANCH_3 = _ResourceRef(tenant_id=2, branch_id=3, name="tenant-2-branch-3")

ALL_RESOURCES = (TENANT_1_BRANCH_1, TENANT_1_BRANCH_2, TENANT_2_BRANCH_3)

# Roles that must never see another tenant's data (ADR-0004).
_TENANT_SCOPED_ROLES = frozenset(
    {
        Role.CONSULTANCY_OWNER,
        Role.BRANCH_MANAGER,
        Role.COUNSELOR,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
        Role.STUDENT,
    }
)

# Roles restricted to a single branch within their tenant (ADR-0004).
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


@pytest.fixture()
def sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def session(sqlite_engine):
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)
    with testing_session_local() as db_session:
        now = datetime.now(timezone.utc)
        db_session.add_all(
            [
                _ScopedResource(
                    tenant_id=resource.tenant_id,
                    branch_id=resource.branch_id,
                    name=resource.name,
                    created_at=now,
                    updated_at=now,
                )
                for resource in ALL_RESOURCES
            ]
        )
        db_session.commit()
        yield db_session


def _scoped_names(session, user: AuthenticatedUser) -> list[str]:
    statement = select(_ScopedResource)
    statement = apply_tenant_scope(statement, _ScopedResource, user)
    statement = apply_branch_scope(statement, _ScopedResource, user)
    rows = session.scalars(statement).all()
    return sorted(row.name for row in rows)


def _user_for_role(role: Role, *, tenant_id: int = 1, branch_id: int = 1) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=1,
        role=role,
        tenant_id=tenant_id if role != Role.SUPER_ADMIN else None,
        branch_id=branch_id if role in _BRANCH_SCOPED_ROLES else None,
    )


@pytest.mark.parametrize("role", sorted(_TENANT_SCOPED_ROLES, key=lambda r: r.value))
def test_cross_tenant_access_denied_for_tenant_scoped_roles(session, role: Role) -> None:
    """Users in tenant 1 must not see tenant 2 resources."""
    user = _user_for_role(role, tenant_id=1, branch_id=1)
    visible = _scoped_names(session, user)
    assert TENANT_2_BRANCH_3.name not in visible
    assert all(name.startswith("tenant-1-") for name in visible)


@pytest.mark.parametrize("role", sorted(_BRANCH_SCOPED_ROLES, key=lambda r: r.value))
def test_cross_branch_access_denied_for_branch_scoped_roles(session, role: Role) -> None:
    """Branch-scoped roles in branch 1 must not see branch 2 resources (same tenant)."""
    user = _user_for_role(role, tenant_id=1, branch_id=1)
    visible = _scoped_names(session, user)
    assert TENANT_1_BRANCH_2.name not in visible
    assert TENANT_1_BRANCH_1.name in visible


def test_super_admin_sees_all_tenants_and_branches(session) -> None:
    user = _user_for_role(Role.SUPER_ADMIN)
    assert _scoped_names(session, user) == sorted(resource.name for resource in ALL_RESOURCES)


def test_consultancy_owner_sees_all_branches_within_tenant_but_not_other_tenants(
    session,
) -> None:
    user = _user_for_role(Role.CONSULTANCY_OWNER, tenant_id=1)
    visible = _scoped_names(session, user)
    assert visible == sorted([TENANT_1_BRANCH_1.name, TENANT_1_BRANCH_2.name])
    assert TENANT_2_BRANCH_3.name not in visible


@pytest.mark.parametrize(
    ("role", "tenant_id", "branch_id", "expected_names"),
    [
        (Role.BRANCH_MANAGER, 1, 2, [TENANT_1_BRANCH_2.name]),
        (Role.COUNSELOR, 1, 2, [TENANT_1_BRANCH_2.name]),
        (Role.DOCUMENT_VERIFIER, 1, 2, [TENANT_1_BRANCH_2.name]),
        (Role.VISA_PROCESSOR, 1, 2, [TENANT_1_BRANCH_2.name]),
        (Role.RECEPTIONIST, 1, 2, [TENANT_1_BRANCH_2.name]),
        (Role.STUDENT, 1, 2, [TENANT_1_BRANCH_2.name]),
    ],
)
def test_branch_scoped_role_sees_only_assigned_branch(
    session,
    role: Role,
    tenant_id: int,
    branch_id: int,
    expected_names: list[str],
) -> None:
    user = _user_for_role(role, tenant_id=tenant_id, branch_id=branch_id)
    assert _scoped_names(session, user) == expected_names
