from datetime import datetime, timezone

import pytest
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.base import Base, TenantScopedBase
from app.rbac import Role
from app.rbac.user import AuthenticatedUser


class _SampleTenantModel(TenantScopedBase):
    __tablename__ = "test_tenant_scope_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


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
                _SampleTenantModel(tenant_id=1, name="tenant-1-a", created_at=now, updated_at=now),
                _SampleTenantModel(tenant_id=1, name="tenant-1-b", created_at=now, updated_at=now),
                _SampleTenantModel(tenant_id=2, name="tenant-2-a", created_at=now, updated_at=now),
            ]
        )
        db_session.commit()
        yield db_session


def _fetch_names(session, user: AuthenticatedUser) -> list[str]:
    statement = apply_tenant_scope(select(_SampleTenantModel), _SampleTenantModel, user)
    rows = session.scalars(statement).all()
    return [row.name for row in rows]


def test_super_admin_sees_all_tenants(session) -> None:
    user = AuthenticatedUser(id=1, role=Role.SUPER_ADMIN, tenant_id=None)
    assert sorted(_fetch_names(session, user)) == ["tenant-1-a", "tenant-1-b", "tenant-2-a"]


def test_tenant_scoped_role_sees_only_own_tenant(session) -> None:
    user = AuthenticatedUser(id=2, role=Role.COUNSELOR, tenant_id=1, branch_id=1)
    assert sorted(_fetch_names(session, user)) == ["tenant-1-a", "tenant-1-b"]


def test_consultancy_owner_sees_only_own_tenant(session) -> None:
    user = AuthenticatedUser(id=3, role=Role.CONSULTANCY_OWNER, tenant_id=2)
    assert _fetch_names(session, user) == ["tenant-2-a"]


def test_non_super_admin_without_tenant_id_raises(session) -> None:
    user = AuthenticatedUser(id=4, role=Role.BRANCH_MANAGER, tenant_id=None, branch_id=1)
    with pytest.raises(TenantScopeError, match="requires tenant_id"):
        _fetch_names(session, user)


def test_apply_tenant_scope_returns_select_for_chaining(session) -> None:
    user = AuthenticatedUser(id=5, role=Role.RECEPTIONIST, tenant_id=1, branch_id=1)
    statement = apply_tenant_scope(select(_SampleTenantModel), _SampleTenantModel, user).where(
        _SampleTenantModel.name == "tenant-1-a"
    )
    row = session.scalars(statement).one()
    assert row.name == "tenant-1-a"
