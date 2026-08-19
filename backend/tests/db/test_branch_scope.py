from datetime import datetime, timezone

import pytest
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.branch_scope import BranchScopeError, apply_branch_scope
from app.models.base import Base, TenantScopedBase
from app.rbac import Role
from app.rbac.user import AuthenticatedUser


class _SampleBranchModel(TenantScopedBase):
    __tablename__ = "test_branch_scope_items"

    branch_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
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
                _SampleBranchModel(
                    tenant_id=1,
                    branch_id=1,
                    name="branch-1-a",
                    created_at=now,
                    updated_at=now,
                ),
                _SampleBranchModel(
                    tenant_id=1,
                    branch_id=1,
                    name="branch-1-b",
                    created_at=now,
                    updated_at=now,
                ),
                _SampleBranchModel(
                    tenant_id=1,
                    branch_id=2,
                    name="branch-2-a",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        db_session.commit()
        yield db_session


def _fetch_names(session, user: AuthenticatedUser) -> list[str]:
    statement = apply_branch_scope(select(_SampleBranchModel), _SampleBranchModel, user)
    rows = session.scalars(statement).all()
    return [row.name for row in rows]


def test_super_admin_sees_all_branches(session) -> None:
    user = AuthenticatedUser(id=1, role=Role.SUPER_ADMIN, tenant_id=None)
    assert sorted(_fetch_names(session, user)) == ["branch-1-a", "branch-1-b", "branch-2-a"]


def test_consultancy_owner_sees_all_branches(session) -> None:
    user = AuthenticatedUser(id=2, role=Role.CONSULTANCY_OWNER, tenant_id=1)
    assert sorted(_fetch_names(session, user)) == ["branch-1-a", "branch-1-b", "branch-2-a"]


def test_branch_scoped_role_sees_only_own_branch(session) -> None:
    user = AuthenticatedUser(id=3, role=Role.COUNSELOR, tenant_id=1, branch_id=1)
    assert sorted(_fetch_names(session, user)) == ["branch-1-a", "branch-1-b"]


def test_branch_manager_sees_only_own_branch(session) -> None:
    user = AuthenticatedUser(id=4, role=Role.BRANCH_MANAGER, tenant_id=1, branch_id=2)
    assert _fetch_names(session, user) == ["branch-2-a"]


def test_branch_scoped_role_without_branch_id_raises(session) -> None:
    user = AuthenticatedUser(id=5, role=Role.RECEPTIONIST, tenant_id=1, branch_id=None)
    with pytest.raises(BranchScopeError, match="requires branch_id"):
        _fetch_names(session, user)


def test_apply_branch_scope_returns_select_for_chaining(session) -> None:
    user = AuthenticatedUser(id=6, role=Role.DOCUMENT_VERIFIER, tenant_id=1, branch_id=1)
    statement = apply_branch_scope(select(_SampleBranchModel), _SampleBranchModel, user).where(
        _SampleBranchModel.name == "branch-1-a"
    )
    row = session.scalars(statement).one()
    assert row.name == "branch-1-a"
