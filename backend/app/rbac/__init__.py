from app.rbac.dependencies import get_current_user, require_permission, require_role
from app.rbac.hierarchy import (
    ROLE_RANK,
    RoleHierarchyError,
    assert_can_act_on_user,
    can_act_on_role,
    can_act_on_user,
    get_role_rank,
)
from app.rbac.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    get_permissions_for_role,
    role_has_permission,
)
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser

__all__ = [
    "AuthenticatedUser",
    "Role",
    "Permission",
    "ROLE_PERMISSIONS",
    "ROLE_RANK",
    "RoleHierarchyError",
    "assert_can_act_on_user",
    "can_act_on_role",
    "can_act_on_user",
    "get_current_user",
    "get_permissions_for_role",
    "get_role_rank",
    "require_permission",
    "require_role",
    "role_has_permission",
]
