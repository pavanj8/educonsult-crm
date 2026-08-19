"""Demo seed runner — validates and loads the canonical demo catalog."""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.seed.catalog import DemoCatalog, DemoUserRecord, get_demo_catalog


@dataclass(frozen=True, slots=True)
class SeedResult:
    tenant_count: int
    branch_count: int
    user_count: int
    roles_seeded: tuple[Role, ...]


class SeedValidationError(ValueError):
    """Raised when the demo catalog fails completeness checks."""


def validate_demo_catalog(catalog: DemoCatalog) -> tuple[Role, ...]:
    """Ensure the catalog covers all roles and multiple tenants."""
    if len(catalog.tenants) < 2:
        raise SeedValidationError("demo catalog must include at least two tenants")

    tenant_ids = {tenant.id for tenant in catalog.tenants}
    if len(tenant_ids) != len(catalog.tenants):
        raise SeedValidationError("demo tenant IDs must be unique")

    branch_tenant_ids = {branch.tenant_id for branch in catalog.branches}
    if not branch_tenant_ids.issubset(tenant_ids):
        raise SeedValidationError("every branch must belong to a demo tenant")

    emails = [user.email.lower() for user in catalog.users]
    if len(emails) != len(set(emails)):
        raise SeedValidationError("demo user emails must be unique")

    roles_present = {user.role for user in catalog.users}
    missing_roles = sorted(set(Role) - roles_present, key=lambda role: role.value)
    if missing_roles:
        missing = ", ".join(role.value for role in missing_roles)
        raise SeedValidationError(f"demo catalog missing roles: {missing}")

    if Role.SUPER_ADMIN not in roles_present:
        raise SeedValidationError("demo catalog must include a super admin user")

    super_admins = [user for user in catalog.users if user.role == Role.SUPER_ADMIN]
    if any(user.tenant_id is not None for user in super_admins):
        raise SeedValidationError("super admin demo users must not have a tenant_id")

    for user in catalog.users:
        _validate_user_scope(user, tenant_ids)

    return tuple(sorted(roles_present, key=lambda role: role.value))


def _validate_user_scope(user: DemoUserRecord, tenant_ids: set[int]) -> None:
    if user.role == Role.SUPER_ADMIN:
        if user.tenant_id is not None or user.branch_id is not None:
            raise SeedValidationError("super admin must have null tenant_id and branch_id")
        return

    if user.tenant_id is None or user.tenant_id not in tenant_ids:
        raise SeedValidationError(f"user {user.email} has invalid tenant_id")

    if user.role == Role.CONSULTANCY_OWNER:
        if user.branch_id is not None:
            raise SeedValidationError(f"owner {user.email} must not have branch_id")
        return

    if user.branch_id is None:
        raise SeedValidationError(f"branch-scoped user {user.email} must have branch_id")


def demo_user_to_authenticated_user(user: DemoUserRecord) -> AuthenticatedUser:
    """Convert a demo catalog user into an ``AuthenticatedUser`` for RBAC tests."""
    return AuthenticatedUser(
        id=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


def seed_demo_data(session: Session | None = None, *, catalog: DemoCatalog | None = None) -> SeedResult:
    """Validate and load the demo catalog.

    Persistence to tenant/user tables is deferred until those models land in
    E5/E8; this runner validates completeness and verifies DB connectivity
    when a session is supplied.
    """
    resolved_catalog = catalog or get_demo_catalog()
    roles_seeded = validate_demo_catalog(resolved_catalog)

    if session is not None:
        session.execute(text("SELECT 1"))

    return SeedResult(
        tenant_count=len(resolved_catalog.tenants),
        branch_count=len(resolved_catalog.branches),
        user_count=len(resolved_catalog.users),
        roles_seeded=roles_seeded,
    )
