"""Demo seed data for all roles and tenants (E3)."""

from app.seed.catalog import (
    DEMO_PASSWORD,
    PRIMARY_DEMO_EMAIL,
    DemoBranchRecord,
    DemoCatalog,
    DemoTenantRecord,
    DemoUserRecord,
    build_demo_catalog,
    get_demo_catalog,
    user_by_email,
    users_for_role,
)
from app.seed.runner import (
    SeedResult,
    SeedValidationError,
    demo_user_to_authenticated_user,
    seed_demo_data,
    seed_demo_data_if_empty,
    validate_demo_catalog,
)

__all__ = [
    "DEMO_PASSWORD",
    "PRIMARY_DEMO_EMAIL",
    "DemoBranchRecord",
    "DemoCatalog",
    "DemoTenantRecord",
    "DemoUserRecord",
    "SeedResult",
    "SeedValidationError",
    "build_demo_catalog",
    "demo_user_to_authenticated_user",
    "get_demo_catalog",
    "seed_demo_data",
    "seed_demo_data_if_empty",
    "user_by_email",
    "users_for_role",
    "validate_demo_catalog",
]
