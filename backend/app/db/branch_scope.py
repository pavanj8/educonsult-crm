"""Branch-scoping query filter helpers (ADR-0001, ADR-0004)."""

from typing import Protocol, TypeVar

from sqlalchemy import Select
from sqlalchemy.orm import Mapped

from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser


class _BranchScoped(Protocol):
    branch_id: Mapped[int]


BranchScopedModel = TypeVar("BranchScopedModel", bound=_BranchScoped)


class BranchScopeError(ValueError):
    """Raised when branch scoping cannot be applied safely."""


_CROSS_BRANCH_ROLES = frozenset({Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER})


def apply_branch_scope(
    statement: Select[tuple[BranchScopedModel]],
    model: type[BranchScopedModel],
    user: AuthenticatedUser,
) -> Select[tuple[BranchScopedModel]]:
    """Restrict a SELECT to the caller's branch unless they have cross-branch visibility.

    Super Admin and Consultancy Owner queries are unfiltered by branch. All other
    roles must carry a ``branch_id``; their queries are filtered to that branch.
    """
    if user.role in _CROSS_BRANCH_ROLES:
        return statement

    if user.branch_id is None:
        raise BranchScopeError(
            f"User with role {user.role.value} requires branch_id for branch-scoped queries"
        )

    return statement.where(model.branch_id == user.branch_id)
