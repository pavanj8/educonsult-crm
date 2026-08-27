import json
import sys
from subprocess import run

import pytest

from app.pipeline.stages import PipelineStage
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
    catalog = get_demo_catalog()
    result = seed_demo_data(session=None)
    assert result.tenant_count == 2
    assert result.branch_count == 4
    # Derived, not a literal: the demo population grows whenever a dashboard
    # needs more shape, and that should not fail this test.
    assert result.user_count == len(catalog.users)
    assert result.application_count == len(catalog.applications)
    assert len(result.roles_seeded) == len(Role)


def test_seed_demo_data_with_session(db_session) -> None:
    catalog = get_demo_catalog()
    result = seed_demo_data(session=db_session)
    assert result.user_count == len(catalog.users)
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
        applications=catalog.applications,
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


def test_demo_catalog_includes_applications_for_both_tenants() -> None:
    catalog = get_demo_catalog()
    assert len(catalog.applications) >= 20

    tenant_ids = {application.tenant_id for application in catalog.applications}
    assert tenant_ids == {1, 2}, "both tenants need data or tenant scoping is untestable"


def test_demo_applications_cover_every_pipeline_stage() -> None:
    # The conversion funnel renders one row per stage; a gap here shows up as a
    # hole in the chart rather than as a failure.
    catalog = get_demo_catalog()
    stages = {application.stage for application in catalog.applications}
    assert stages == set(PipelineStage)


def test_demo_applications_span_multiple_branches_per_tenant() -> None:
    # Cross-branch comparison needs more than one branch per tenant to compare.
    catalog = get_demo_catalog()
    for tenant_id in (1, 2):
        branches = {
            application.branch_id
            for application in catalog.applications
            if application.tenant_id == tenant_id
        }
        assert len(branches) >= 2, f"tenant {tenant_id} has applications in only one branch"


def test_demo_applications_are_dated_relative_to_the_seed_run() -> None:
    # Absolute dates would drift out of the dashboards' rolling filters as time
    # passed, leaving the demo looking empty.
    catalog = get_demo_catalog()
    ages = [application.created_days_ago for application in catalog.applications]
    assert min(ages) >= 0
    assert max(ages) <= 90
    assert max(ages) - min(ages) >= 30, "ages too bunched for a time series to have shape"


def test_demo_applications_reference_seeded_rows() -> None:
    catalog = get_demo_catalog()
    user_ids = {user.id for user in catalog.users}
    branch_ids = {branch.id for branch in catalog.branches}
    program_ids = {program.id for program in catalog.programs}
    university_ids = {university.id for university in catalog.universities}

    for application in catalog.applications:
        assert application.student_id in user_ids
        assert application.assigned_counselor_id in user_ids
        assert application.branch_id in branch_ids
        assert application.program_id in program_ids
        assert application.university_id in university_ids


def test_demo_students_are_spread_over_time() -> None:
    # Registrations-over-time counts student rows by created_at, so students
    # all seeded at once leave that chart flat however much other data exists.
    catalog = get_demo_catalog()
    students = [user for user in catalog.users if user.role == Role.STUDENT]
    assert len(students) >= 10

    ages = sorted(student.created_days_ago for student in students)
    assert max(ages) - min(ages) >= 30, "student registrations too bunched to plot"
    assert len(set(ages)) >= 8, "too many students share a registration date"


def test_demo_students_exist_in_both_tenants() -> None:
    catalog = get_demo_catalog()
    tenants = {user.tenant_id for user in catalog.users if user.role == Role.STUDENT}
    assert tenants == {1, 2}
