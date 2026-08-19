from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.rbac.permissions import Permission, role_has_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser


def get_current_user() -> AuthenticatedUser:
    """Return the authenticated user. JWT verification is wired in E5 (auth login)."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(*allowed_roles: Role) -> Callable[..., AuthenticatedUser]:
    """FastAPI dependency factory: allow only users whose role is in *allowed_roles*."""

    def _require_role(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current_user

    return _require_role


def require_permission(permission: Permission) -> Callable[..., AuthenticatedUser]:
    """FastAPI dependency factory: allow only users whose role grants *permission*."""

    def _require_permission(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if not role_has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _require_permission
