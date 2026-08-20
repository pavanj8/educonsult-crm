import json
import sys
from subprocess import run

import pytest

from app.rbac import Role
from app.rbac.user import AuthenticatedUser
from app.seed import (
    DEMO_PASSWORD,
    PRIMARY_DEMO_EMAIL,
    SeedValidationError,
    demo_user_to_authenticated_user,
    get_demo_catalog,
    seed_demo_data,
    user_by_email,
    users_for_role,
    validate_demo_catalog,
)


def test_demo_catalog_includes_master_data() -> None:
    catalog = get_demo_catalog()
    assert len(catalog.countries) >= 1
    assert len(catalog.universities) >= 1
    assert len(catalog.programs) >= 1
    apex_countries = [country for country in catalog.countries if country.tenant_id == 1]
    assert any(country.name == "Canada" for country in apex_countries)


def test_demo_catalog_includes_two_tenants() -> None:
    catalog = get_demo_catalog()
    assert len(catalog.tenants) == 2
    assert {tenant.slug for tenant in catalog.tenants} == {"apex", "globalreach"}


def test_demo_catalog_covers_all_roles() -> None:
    catalog = get_demo_catalog()
    roles = {user.role for user in catalog.users}
    assert roles == set(Role)


def test_demo_catalog_emails_are_unique() -> None:
    catalog = get_demo_catalog()
    emails = [user.email.lower() for user in catalog.users]
    assert len(emails) == len(set(emails))


def test_primary_demo_login_matches_frontend_e2e() -> None:
    user = user_by_email(PRIMARY_DEMO_EMAIL)
    assert user is not None
    assert user.password == DEMO_PASSWORD
    assert user.role == Role.COUNSELOR


def test_users_for_role_filters_by_tenant() -> None:
    counselors = users_for_role(Role.COUNSELOR)
    assert len(counselors) == 2

    apex_counselors = users_for_role(Role.COUNSELOR, tenant_id=1)
    assert len(apex_counselors) == 1
    assert apex_counselors[0].email == PRIMARY_DEMO_EMAIL


def test_demo_user_to_authenticated_user_preserves_scope() -> None:
    user = user_by_email("manager.mumbai@apex.demo.test")
    assert user is not None
    assert demo_user_to_authenticated_user(user) == AuthenticatedUser(
        id=user.id,
        role=Role.BRANCH_MANAGER,
        tenant_id=1,
        branch_id=1,
    )


def test_validate_demo_catalog_returns_all_roles() -> None:
    roles = validate_demo_catalog(get_demo_catalog())
    assert roles == tuple(sorted(Role, key=lambda role: role.value))


def test_seed_demo_data_without_session() -> None:
    result = seed_demo_data(session=None)
    assert result.tenant_count == 2
    assert result.branch_count == 4
    assert result.user_count == 15
    assert len(result.roles_seeded) == len(Role)


def test_seed_demo_data_with_session(db_session) -> None:
    result = seed_demo_data(session=db_session)
    assert result.user_count == 15
    assert result.country_count == 3
    assert result.university_count == 4
    assert result.program_count == 4


def test_seed_demo_data_rejects_incomplete_catalog() -> None:
    catalog = get_demo_catalog()
    incomplete_users = tuple(user for user in catalog.users if user.role != Role.STUDENT)
    broken = catalog.__class__(
        tenants=catalog.tenants,
        branches=catalog.branches,
        users=incomplete_users,
        countries=catalog.countries,
        universities=catalog.universities,
        programs=catalog.programs,
    )
    with pytest.raises(SeedValidationError, match="missing roles"):
        seed_demo_data(session=None, catalog=broken)


def test_seed_cli_validate_only_exits_zero() -> None:
    completed = run(
        [sys.executable, "-m", "app.seed", "--validate-only", "--json"],
        check=False,
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["tenant_count"] == 2
    assert payload["primary_login_email"] == PRIMARY_DEMO_EMAIL
    assert set(payload["roles"]) == {role.value for role in Role}
