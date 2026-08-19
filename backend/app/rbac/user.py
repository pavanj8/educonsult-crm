from dataclasses import dataclass

from app.rbac.roles import Role


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Authenticated principal used by RBAC dependencies (populated from JWT in E5)."""

    id: int
    role: Role
    tenant_id: int | None = None
    branch_id: int | None = None
