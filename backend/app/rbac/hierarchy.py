"""Role hierarchy enforcement: who may perform management actions on whom (ADR-0004)."""

from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser

# Numeric rank per role; higher rank may act on strictly lower ranks.
# Operational staff roles share the same rank (peers cannot manage each other).
ROLE_RANK: dict[Role, int] = {
    Role.SUPER_ADMIN: 100,
    Role.CONSULTANCY_OWNER: 80,
    Role.BRANCH_MANAGER: 60,
    Role.COUNSELOR: 40,
    Role.DOCUMENT_VERIFIER: 40,
    Role.VISA_PROCESSOR: 40,
    Role.RECEPTIONIST: 40,
    Role.STUDENT: 20,
}

_CROSS_BRANCH_ACTOR_ROLES = frozenset({Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER})


class RoleHierarchyError(ValueError):
    """Raised when role hierarchy or scope prevents a management action."""


def get_role_rank(role: Role) -> int:
    """Return the hierarchy rank for *role*."""
    return ROLE_RANK[role]


def can_act_on_role(actor_role: Role, target_role: Role) -> bool:
    """Return whether *actor_role* may manage users with *target_role*.

    Rules (Requirements §3, ADR-0004):
    - Actors must strictly outrank their target; peers and superiors are denied.
    - Only Super Admin may manage another Super Admin.
    - Students are outside the staff hierarchy and are not manageable via these rules.
    """
    if actor_role == target_role:
        return False

    if target_role == Role.STUDENT:
        return False

    if target_role == Role.SUPER_ADMIN:
        return actor_role == Role.SUPER_ADMIN

    if actor_role == Role.STUDENT:
        return False

    return get_role_rank(actor_role) > get_role_rank(target_role)


def can_act_on_user(
    actor: AuthenticatedUser,
    *,
    target_role: Role,
    target_tenant_id: int | None,
    target_branch_id: int | None,
) -> bool:
    """Return whether *actor* may manage a user with the given role and scope.

    Combines role hierarchy with tenant and branch scoping (E12/E13):
    - Super Admin is unscoped by tenant.
    - Consultancy Owner may act across branches within their tenant.
    - Branch Manager may act only on users in their own branch.
    """
    if not can_act_on_role(actor.role, target_role):
        return False

    if actor.role == Role.SUPER_ADMIN:
        return True

    if actor.tenant_id is None or target_tenant_id is None:
        return False

    if actor.tenant_id != target_tenant_id:
        return False

    if actor.role in _CROSS_BRANCH_ACTOR_ROLES:
        return True

    if actor.role == Role.BRANCH_MANAGER:
        if actor.branch_id is None or target_branch_id is None:
            return False
        return actor.branch_id == target_branch_id

    return False


def assert_can_act_on_user(
    actor: AuthenticatedUser,
    *,
    target_role: Role,
    target_tenant_id: int | None,
    target_branch_id: int | None,
) -> None:
    """Raise RoleHierarchyError when *actor* may not manage the target user."""
    if actor.role != Role.SUPER_ADMIN and actor.tenant_id is None:
        raise RoleHierarchyError(
            f"User with role {actor.role.value} requires tenant_id to act on other users"
        )

    if actor.role == Role.BRANCH_MANAGER and actor.branch_id is None:
        raise RoleHierarchyError(
            f"User with role {actor.role.value} requires branch_id to act on other users"
        )

    if not can_act_on_user(
        actor,
        target_role=target_role,
        target_tenant_id=target_tenant_id,
        target_branch_id=target_branch_id,
    ):
        raise RoleHierarchyError(
            f"Role {actor.role.value} cannot act on user with role {target_role.value}"
        )
