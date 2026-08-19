from datetime import datetime, timezone

import pytest
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.rbac import Role
from app.rbac.user import AuthenticatedUser
from tests.factories import (
    BranchResourceSpec,
    TenantResourceSpec,
    make_authenticated_user,
    make_scoped_timestamps,
    next_test_id,
    reset_test_ids,
    seed_branch_scoped_models,
    seed_tenant_scoped_models,
    utc_now,
)
from app.models.base import TenantScopedBase


class _TenantOnlyProbe(TenantScopedBase):
    __tablename__ = "test_factory_tenant_probe_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class _BranchProbe(TenantScopedBase):
    __tablename__ = "test_factory_branch_probe_items"

    branch_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


@pytest.fixture(autouse=True)
def _reset_factory_ids() -> None:
    reset_test_ids()


def test_next_test_id_increments() -> None:
    assert next_test_id() == 1
    assert next_test_id() == 2


def test_reset_test_ids_sets_sequence_start() -> None:
    next_test_id()
    next_test_id()
    reset_test_ids(start=100)
    assert next_test_id() == 100


def test_utc_now_is_timezone_aware() -> None:
    now = utc_now()
    assert now.tzinfo == timezone.utc


def test_make_scoped_timestamps_defaults_to_matching_pair() -> None:
    created_at, updated_at = make_scoped_timestamps()
    assert created_at == updated_at
    assert created_at.tzinfo == timezone.utc


def test_make_scoped_timestamps_accepts_explicit_timestamp() -> None:
    explicit = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    created_at, updated_at = make_scoped_timestamps(explicit)
    assert created_at == explicit
    assert updated_at == explicit


@pytest.mark.parametrize(
    ("role", "expected_tenant_id", "expected_branch_id"),
    [
        (Role.SUPER_ADMIN, None, None),
        (Role.CONSULTANCY_OWNER, 1, None),
        (Role.BRANCH_MANAGER, 1, 1),
        (Role.COUNSELOR, 1, 1),
        (Role.STUDENT, 1, 1),
    ],
)
def test_make_authenticated_user_applies_role_scoping_defaults(
    role: Role,
    expected_tenant_id: int | None,
    expected_branch_id: int | None,
) -> None:
    user = make_authenticated_user(role, user_id=42)
    assert user == AuthenticatedUser(
        id=42,
        role=role,
        tenant_id=expected_tenant_id,
        branch_id=expected_branch_id,
    )


def test_make_authenticated_user_assigns_incrementing_ids_by_default() -> None:
    first = make_authenticated_user(Role.COUNSELOR)
    second = make_authenticated_user(Role.RECEPTIONIST)
    assert first.id == 1
    assert second.id == 2


def test_make_authenticated_user_allows_explicit_none_scope_overrides() -> None:
    user = make_authenticated_user(
        Role.BRANCH_MANAGER,
        user_id=7,
        tenant_id=None,
        branch_id=None,
    )
    assert user.tenant_id is None
    assert user.branch_id is None


def test_seed_tenant_scoped_models_persists_rows(db_session) -> None:
    rows = seed_tenant_scoped_models(
        db_session,
        _TenantOnlyProbe,
        [
            TenantResourceSpec(tenant_id=1, name="tenant-1-a"),
            TenantResourceSpec(tenant_id=2, name="tenant-2-a"),
        ],
    )
    assert len(rows) == 2
    assert rows[0].id is not None
    assert rows[0].tenant_id == 1
    assert rows[0].name == "tenant-1-a"
    assert rows[1].tenant_id == 2


def test_seed_branch_scoped_models_persists_rows(db_session) -> None:
    rows = seed_branch_scoped_models(
        db_session,
        _BranchProbe,
        [
            BranchResourceSpec(tenant_id=1, branch_id=1, name="branch-1"),
            BranchResourceSpec(tenant_id=1, branch_id=2, name="branch-2"),
        ],
    )
    assert len(rows) == 2
    assert rows[0].branch_id == 1
    assert rows[1].branch_id == 2
