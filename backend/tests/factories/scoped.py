from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

from sqlalchemy.orm import Session

from app.models.base import TenantScopedBase
from tests.factories.timestamps import utc_now

TenantScopedModel = TypeVar("TenantScopedModel", bound=TenantScopedBase)


@dataclass(frozen=True, slots=True)
class TenantResourceSpec:
    tenant_id: int
    name: str


@dataclass(frozen=True, slots=True)
class BranchResourceSpec:
    tenant_id: int
    branch_id: int
    name: str


def make_scoped_timestamps(at: datetime | None = None) -> tuple[datetime, datetime]:
    """Return ``(created_at, updated_at)`` for tenant-scoped models."""
    timestamp = at or utc_now()
    return timestamp, timestamp


def seed_tenant_scoped_models(
    session: Session,
    model_cls: type[TenantScopedModel],
    specs: Sequence[TenantResourceSpec],
    *,
    at: datetime | None = None,
) -> list[TenantScopedModel]:
    """Insert tenant-scoped rows and return the persisted instances."""
    created_at, updated_at = make_scoped_timestamps(at)
    rows = [
        model_cls(
            tenant_id=spec.tenant_id,
            name=spec.name,
            created_at=created_at,
            updated_at=updated_at,
        )
        for spec in specs
    ]
    session.add_all(rows)
    session.commit()
    for row in rows:
        session.refresh(row)
    return rows


def seed_branch_scoped_models(
    session: Session,
    model_cls: type[TenantScopedModel],
    specs: Sequence[BranchResourceSpec],
    *,
    at: datetime | None = None,
) -> list[TenantScopedModel]:
    """Insert branch-scoped rows (models must define ``branch_id``) and return them."""
    created_at, updated_at = make_scoped_timestamps(at)
    rows = [
        model_cls(
            tenant_id=spec.tenant_id,
            branch_id=spec.branch_id,
            name=spec.name,
            created_at=created_at,
            updated_at=updated_at,
        )
        for spec in specs
    ]
    session.add_all(rows)
    session.commit()
    for row in rows:
        session.refresh(row)
    return rows
