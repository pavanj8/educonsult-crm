"""Tenant-scoping query filter helpers (ADR-0001, ADR-0004)."""

from typing import TypeVar

from sqlalchemy import Select

from app.models.base import TenantScopedBase
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser

TenantScopedModel = TypeVar("TenantScopedModel", bound=TenantScopedBase)


class TenantScopeError(ValueError):
    """Raised when tenant scoping cannot be applied safely."""


def apply_tenant_scope(
    statement: Select[tuple[TenantScopedModel]],
    model: type[TenantScopedModel],
    user: AuthenticatedUser,
) -> Select[tuple[TenantScopedModel]]:
    """Restrict a SELECT to the caller's tenant unless they are Super Admin.

    Super Admin queries are unfiltered (platform-wide visibility). All other
    roles must carry a ``tenant_id``; their queries are filtered to that tenant.
    """
    if user.role == Role.SUPER_ADMIN:
        return statement

    if user.tenant_id is None:
        raise TenantScopeError(
            f"User with role {user.role.value} requires tenant_id for tenant-scoped queries"
        )

    return statement.where(model.tenant_id == user.tenant_id)
