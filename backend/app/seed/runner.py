"""Demo seed runner — validates and loads the canonical demo catalog."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.password import hash_password
from app.models.branch import Branch
from app.models.country import Country
from app.models.program import Program
from app.models.tenant import Tenant
from app.models.university import University
from app.models.user import User
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.seed.catalog import DemoCatalog, DemoUserRecord, get_demo_catalog


@dataclass(frozen=True, slots=True)
class SeedResult:
    tenant_count: int
    branch_count: int
    user_count: int
    country_count: int
    university_count: int
    program_count: int
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

    country_tenant_ids = {country.tenant_id for country in catalog.countries}
    if not country_tenant_ids.issubset(tenant_ids):
        raise SeedValidationError("every country must belong to a demo tenant")

    for university in catalog.universities:
        if university.tenant_id not in tenant_ids:
            raise SeedValidationError("every university must belong to a demo tenant")
        if not any(
            country.id == university.country_id and country.tenant_id == university.tenant_id
            for country in catalog.countries
        ):
            raise SeedValidationError(
                f"university {university.id} references unknown country {university.country_id}"
            )

    for program in catalog.programs:
        if program.tenant_id not in tenant_ids:
            raise SeedValidationError("every program must belong to a demo tenant")
        if not any(
            university.id == program.university_id and university.tenant_id == program.tenant_id
            for university in catalog.universities
        ):
            raise SeedValidationError(
                f"program {program.id} references unknown university {program.university_id}"
            )

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


def _persist_demo_catalog(session: Session, catalog: DemoCatalog) -> None:
    now = datetime.now(timezone.utc)
    for tenant_record in catalog.tenants:
        session.add(
            Tenant(
                id=tenant_record.id,
                name=tenant_record.name,
                slug=tenant_record.slug,
                created_at=now,
                updated_at=now,
            )
        )
    for branch_record in catalog.branches:
        session.add(
            Branch(
                id=branch_record.id,
                tenant_id=branch_record.tenant_id,
                name=branch_record.name,
                city=branch_record.city,
                created_at=now,
                updated_at=now,
            )
        )
    for country_record in catalog.countries:
        session.add(
            Country(
                id=country_record.id,
                tenant_id=country_record.tenant_id,
                name=country_record.name,
                code=country_record.code,
                created_at=now,
                updated_at=now,
            )
        )
    for university_record in catalog.universities:
        session.add(
            University(
                id=university_record.id,
                tenant_id=university_record.tenant_id,
                country_id=university_record.country_id,
                name=university_record.name,
                created_at=now,
                updated_at=now,
            )
        )
    for program_record in catalog.programs:
        session.add(
            Program(
                id=program_record.id,
                tenant_id=program_record.tenant_id,
                university_id=program_record.university_id,
                name=program_record.name,
                created_at=now,
                updated_at=now,
            )
        )
    for user_record in catalog.users:
        session.add(
            User(
                id=user_record.id,
                email=user_record.email,
                password_hash=hash_password(user_record.password),
                role=user_record.role,
                tenant_id=user_record.tenant_id,
                branch_id=user_record.branch_id,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()


def seed_demo_data(session: Session | None = None, *, catalog: DemoCatalog | None = None) -> SeedResult:
    """Validate and optionally load the demo catalog into the database."""
    resolved_catalog = catalog or get_demo_catalog()
    roles_seeded = validate_demo_catalog(resolved_catalog)

    if session is not None:
        session.execute(text("SELECT 1"))
        _persist_demo_catalog(session, resolved_catalog)

    return SeedResult(
        tenant_count=len(resolved_catalog.tenants),
        branch_count=len(resolved_catalog.branches),
        user_count=len(resolved_catalog.users),
        country_count=len(resolved_catalog.countries),
        university_count=len(resolved_catalog.universities),
        program_count=len(resolved_catalog.programs),
        roles_seeded=roles_seeded,
    )


def seed_demo_data_if_empty(session: Session) -> SeedResult | None:
    """Load demo data when the database has no tenants (sqlite QA/dev bootstrap)."""
    if session.query(Tenant.id).first() is not None:
        return None
    return seed_demo_data(session=session)
