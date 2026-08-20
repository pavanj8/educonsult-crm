"""Canonical demo data catalog for local development, E2E, and integration tests."""

from dataclasses import dataclass

from app.rbac.roles import Role

DEMO_PASSWORD = "demo-password"

# Matches frontend/e2e/helpers/auth.ts DEMO_LOGIN for the login smoke test.
PRIMARY_DEMO_EMAIL = "counselor@demo.test"


@dataclass(frozen=True, slots=True)
class DemoTenantRecord:
    id: int
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class DemoBranchRecord:
    id: int
    tenant_id: int
    name: str
    city: str


@dataclass(frozen=True, slots=True)
class DemoUserRecord:
    id: int
    email: str
    password: str
    role: Role
    display_name: str
    tenant_id: int | None
    branch_id: int | None


@dataclass(frozen=True, slots=True)
class DemoCountryRecord:
    id: int
    tenant_id: int
    name: str
    code: str


@dataclass(frozen=True, slots=True)
class DemoUniversityRecord:
    id: int
    tenant_id: int
    country_id: int
    name: str


@dataclass(frozen=True, slots=True)
class DemoProgramRecord:
    id: int
    tenant_id: int
    university_id: int
    name: str


@dataclass(frozen=True, slots=True)
class DemoCatalog:
    tenants: tuple[DemoTenantRecord, ...]
    branches: tuple[DemoBranchRecord, ...]
    users: tuple[DemoUserRecord, ...]
    countries: tuple[DemoCountryRecord, ...]
    universities: tuple[DemoUniversityRecord, ...]
    programs: tuple[DemoProgramRecord, ...]


def _user(
    user_id: int,
    email: str,
    role: Role,
    display_name: str,
    *,
    tenant_id: int | None,
    branch_id: int | None,
    password: str = DEMO_PASSWORD,
) -> DemoUserRecord:
    return DemoUserRecord(
        id=user_id,
        email=email,
        password=password,
        role=role,
        display_name=display_name,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )


def build_demo_catalog() -> DemoCatalog:
    """Return the fixed demo dataset covering all platform roles and two tenants."""
    tenants = (
        DemoTenantRecord(id=1, name="Apex EduConsult", slug="apex"),
        DemoTenantRecord(id=2, name="Global Reach Consultancy", slug="globalreach"),
    )
    branches = (
        DemoBranchRecord(id=1, tenant_id=1, name="Mumbai HQ", city="Mumbai"),
        DemoBranchRecord(id=2, tenant_id=1, name="Delhi Center", city="Delhi"),
        DemoBranchRecord(id=3, tenant_id=2, name="Bangalore Office", city="Bangalore"),
        DemoBranchRecord(id=4, tenant_id=2, name="Hyderabad Office", city="Hyderabad"),
    )
    users = (
        _user(
            1,
            "super_admin@demo.test",
            Role.SUPER_ADMIN,
            "Priya Sharma",
            tenant_id=None,
            branch_id=None,
        ),
        _user(
            2,
            "owner@apex.demo.test",
            Role.CONSULTANCY_OWNER,
            "Rajesh Mehta",
            tenant_id=1,
            branch_id=None,
        ),
        _user(
            3,
            "manager.mumbai@apex.demo.test",
            Role.BRANCH_MANAGER,
            "Anita Desai",
            tenant_id=1,
            branch_id=1,
        ),
        _user(
            4,
            PRIMARY_DEMO_EMAIL,
            Role.COUNSELOR,
            "Vikram Patel",
            tenant_id=1,
            branch_id=1,
        ),
        _user(
            5,
            "verifier@apex.demo.test",
            Role.DOCUMENT_VERIFIER,
            "Sneha Iyer",
            tenant_id=1,
            branch_id=1,
        ),
        _user(
            6,
            "visa@apex.demo.test",
            Role.VISA_PROCESSOR,
            "Arjun Singh",
            tenant_id=1,
            branch_id=2,
        ),
        _user(
            7,
            "reception@apex.demo.test",
            Role.RECEPTIONIST,
            "Meera Nair",
            tenant_id=1,
            branch_id=1,
        ),
        _user(
            8,
            "student@apex.demo.test",
            Role.STUDENT,
            "Rahul Kumar",
            tenant_id=1,
            branch_id=1,
        ),
        _user(
            9,
            "owner@globalreach.demo.test",
            Role.CONSULTANCY_OWNER,
            "Kavitha Reddy",
            tenant_id=2,
            branch_id=None,
        ),
        _user(
            10,
            "manager.bangalore@globalreach.demo.test",
            Role.BRANCH_MANAGER,
            "Suresh Rao",
            tenant_id=2,
            branch_id=3,
        ),
        _user(
            11,
            "counselor@globalreach.demo.test",
            Role.COUNSELOR,
            "Deepa Menon",
            tenant_id=2,
            branch_id=3,
        ),
        _user(
            12,
            "verifier@globalreach.demo.test",
            Role.DOCUMENT_VERIFIER,
            "Lakshmi Prasad",
            tenant_id=2,
            branch_id=4,
        ),
        _user(
            13,
            "visa@globalreach.demo.test",
            Role.VISA_PROCESSOR,
            "Mohammed Ali",
            tenant_id=2,
            branch_id=4,
        ),
        _user(
            14,
            "reception@globalreach.demo.test",
            Role.RECEPTIONIST,
            "Pooja Shah",
            tenant_id=2,
            branch_id=3,
        ),
        _user(
            15,
            "student@globalreach.demo.test",
            Role.STUDENT,
            "Aisha Khan",
            tenant_id=2,
            branch_id=3,
        ),
    )
    countries = (
        DemoCountryRecord(id=1, tenant_id=1, name="Canada", code="CA"),
        DemoCountryRecord(id=2, tenant_id=1, name="United Kingdom", code="GB"),
        DemoCountryRecord(id=3, tenant_id=2, name="Australia", code="AU"),
    )
    universities = (
        DemoUniversityRecord(
            id=10,
            tenant_id=1,
            country_id=1,
            name="University of Toronto",
        ),
        DemoUniversityRecord(
            id=11,
            tenant_id=1,
            country_id=1,
            name="University of British Columbia",
        ),
        DemoUniversityRecord(
            id=20,
            tenant_id=1,
            country_id=2,
            name="University of Manchester",
        ),
        DemoUniversityRecord(
            id=30,
            tenant_id=2,
            country_id=3,
            name="University of Melbourne",
        ),
    )
    programs = (
        DemoProgramRecord(
            id=100,
            tenant_id=1,
            university_id=10,
            name="Computer Science MSc",
        ),
        DemoProgramRecord(
            id=101,
            tenant_id=1,
            university_id=10,
            name="Business Administration MBA",
        ),
        DemoProgramRecord(
            id=110,
            tenant_id=1,
            university_id=11,
            name="Data Science MSc",
        ),
        DemoProgramRecord(
            id=200,
            tenant_id=2,
            university_id=30,
            name="Engineering PhD",
        ),
    )
    return DemoCatalog(
        tenants=tenants,
        branches=branches,
        users=users,
        countries=countries,
        universities=universities,
        programs=programs,
    )


_DEMO_CATALOG: DemoCatalog | None = None


def get_demo_catalog() -> DemoCatalog:
    """Return the singleton demo catalog instance."""
    global _DEMO_CATALOG
    if _DEMO_CATALOG is None:
        _DEMO_CATALOG = build_demo_catalog()
    return _DEMO_CATALOG


def users_for_role(role: Role, *, tenant_id: int | None = None) -> tuple[DemoUserRecord, ...]:
    """Return demo users matching ``role`` and optional ``tenant_id`` filter."""
    catalog = get_demo_catalog()
    matches = [user for user in catalog.users if user.role == role]
    if tenant_id is not None:
        matches = [user for user in matches if user.tenant_id == tenant_id]
    return tuple(matches)


def user_by_email(email: str) -> DemoUserRecord | None:
    """Look up a demo user by email address."""
    normalized = email.strip().lower()
    for user in get_demo_catalog().users:
        if user.email.lower() == normalized:
            return user
    return None
