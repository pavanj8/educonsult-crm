"""Canonical demo data catalog for local development, E2E, and integration tests."""

from dataclasses import dataclass

from app.pipeline.stages import PipelineStage
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
    #: Age in days at seed time, as for applications. Registrations-over-time
    #: counts student rows by ``created_at``, so students seeded all at once
    #: leave that chart flat no matter how much other data exists.
    created_days_ago: int = 0


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
class DemoApplicationRecord:
    id: int
    tenant_id: int
    branch_id: int
    student_id: int
    assigned_counselor_id: int
    university_id: int
    program_id: int
    stage: PipelineStage
    #: Age in days at seed time. Relative rather than absolute so the demo data
    #: keeps landing inside the dashboards' rolling date filters however long
    #: after this catalog was written the seed is run.
    created_days_ago: int
    loan_opt_in: bool = False


@dataclass(frozen=True, slots=True)
class DemoCatalog:
    tenants: tuple[DemoTenantRecord, ...]
    branches: tuple[DemoBranchRecord, ...]
    users: tuple[DemoUserRecord, ...]
    countries: tuple[DemoCountryRecord, ...]
    universities: tuple[DemoUniversityRecord, ...]
    programs: tuple[DemoProgramRecord, ...]
    applications: tuple[DemoApplicationRecord, ...]


def _user(
    user_id: int,
    email: str,
    role: Role,
    display_name: str,
    *,
    tenant_id: int | None,
    branch_id: int | None,
    password: str = DEMO_PASSWORD,
    created_days_ago: int = 0,
) -> DemoUserRecord:
    return DemoUserRecord(
        id=user_id,
        email=email,
        password=password,
        role=role,
        display_name=display_name,
        tenant_id=tenant_id,
        branch_id=branch_id,
        created_days_ago=created_days_ago,
    )


def _demo_students() -> tuple[DemoUserRecord, ...]:
    """Additional student accounts, spread over the last two months.

    The named staff accounts above are the ones people sign in as; these exist
    so the registrations-over-time chart has a population to count. Each row is
    a student who registered N days ago, weighted towards the recent end the
    way a growing consultancy's intake would be.
    """
    # (id, tenant, branch, name, days ago)
    rows: tuple[tuple[int, int, int, str, int], ...] = (
        (40, 1, 1, "Ananya Bose", 1),
        (41, 1, 1, "Karthik Menon", 3),
        (42, 1, 2, "Farah Sheikh", 4),
        (43, 1, 1, "Devansh Gupta", 7),
        (44, 1, 2, "Ishita Rao", 10),
        (45, 1, 1, "Nikhil Verma", 13),
        (46, 1, 1, "Sanjana Pillai", 18),
        (47, 1, 2, "Rohan D'Souza", 24),
        (48, 1, 1, "Tanvi Joshi", 31),
        (49, 1, 2, "Aditya Nair", 39),
        (50, 1, 1, "Preeti Chawla", 48),
        (51, 1, 1, "Zoya Ahmed", 57),
        (60, 2, 3, "Harish Kumar", 6),
        (61, 2, 4, "Divya Sundaram", 15),
        (62, 2, 3, "Manish Agarwal", 27),
        (63, 2, 4, "Ritika Bansal", 41),
    )
    return tuple(
        _user(
            user_id,
            f"student{user_id}@{'apex' if tenant_id == 1 else 'globalreach'}.demo.test",
            Role.STUDENT,
            display_name,
            tenant_id=tenant_id,
            branch_id=branch_id,
            created_days_ago=days_ago,
        )
        for user_id, tenant_id, branch_id, display_name, days_ago in rows
    )


def _applications() -> tuple[DemoApplicationRecord, ...]:
    """Applications for both tenants, shaped so the analytics views mean something.

    Every dashboard on the platform is computed from this table, so the demo
    data has to carry shape rather than volume:

    * counts taper down the pipeline, so the conversion funnel looks like a
      funnel instead of a flat bar chart;
    * Apex is split unevenly across Mumbai HQ and Delhi Center, so the
      cross-branch comparison has something to compare;
    * ages are spread across roughly two months, so registrations-over-time has
      a curve and the shorter rolling filters are not empty;
    * Global Reach carries its own smaller set, so tenant scoping is visibly
      doing something rather than trivially true.
    """
    S = PipelineStage
    # (branch, stage, days ago) for Apex (tenant 1). Mumbai HQ carries the
    # bulk; Delhi Center is the smaller, newer office.
    apex: tuple[tuple[int, PipelineStage, int], ...] = (
        (1, S.REGISTERED, 2), (1, S.REGISTERED, 4), (1, S.REGISTERED, 9),
        (2, S.REGISTERED, 3), (2, S.REGISTERED, 12),
        (1, S.COUNSELING, 6), (1, S.COUNSELING, 14), (1, S.COUNSELING, 21),
        (2, S.COUNSELING, 8),
        (1, S.UNIVERSITY_SHORTLISTING, 17), (1, S.UNIVERSITY_SHORTLISTING, 26),
        (2, S.UNIVERSITY_SHORTLISTING, 23),
        (1, S.APPLICATION_SUBMITTED, 24), (1, S.APPLICATION_SUBMITTED, 33),
        (2, S.APPLICATION_SUBMITTED, 29),
        (1, S.DOCUMENT_VERIFICATION, 31), (2, S.DOCUMENT_VERIFICATION, 38),
        (1, S.OFFER_LETTER, 36), (1, S.OFFER_LETTER, 44),
        (1, S.VISA_PROCESSING, 41), (2, S.VISA_PROCESSING, 47),
        (1, S.LOAN_PROCESSING, 45),
        (1, S.ENROLLED, 50), (1, S.ENROLLED, 55), (2, S.ENROLLED, 58),
        (1, S.REJECTED, 27), (2, S.REJECTED, 43),
        (1, S.WITHDRAWN, 35),
    )
    # (branch, stage, days ago) for Global Reach (tenant 2).
    globalreach: tuple[tuple[int, PipelineStage, int], ...] = (
        (3, S.REGISTERED, 5), (3, S.REGISTERED, 11),
        (3, S.COUNSELING, 16), (4, S.COUNSELING, 22),
        (4, S.APPLICATION_SUBMITTED, 30),
        (3, S.ENROLLED, 46), (4, S.ENROLLED, 53),
        (4, S.REJECTED, 39),
    )

    records: list[DemoApplicationRecord] = []
    next_id = 1000

    # Apex cycles its three programmes so the university/programme mix is not
    # uniform; Global Reach has only the one on offer.
    apex_programs = ((10, 100), (10, 101), (11, 110))
    # Spread across the student pool rather than piling every application onto
    # the one named demo student, so per-student views are not all-or-nothing.
    apex_students = tuple(
        student.id for student in _demo_students() if student.tenant_id == 1
    )
    for index, (branch_id, stage, days_ago) in enumerate(apex):
        university_id, program_id = apex_programs[index % len(apex_programs)]
        records.append(
            DemoApplicationRecord(
                id=next_id,
                tenant_id=1,
                branch_id=branch_id,
                student_id=apex_students[index % len(apex_students)],
                assigned_counselor_id=4,
                university_id=university_id,
                program_id=program_id,
                stage=stage,
                created_days_ago=days_ago,
                loan_opt_in=stage is S.LOAN_PROCESSING,
            )
        )
        next_id += 1

    globalreach_students = tuple(
        student.id for student in _demo_students() if student.tenant_id == 2
    )
    for index, (branch_id, stage, days_ago) in enumerate(globalreach):
        records.append(
            DemoApplicationRecord(
                id=next_id,
                tenant_id=2,
                branch_id=branch_id,
                student_id=globalreach_students[index % len(globalreach_students)],
                assigned_counselor_id=11,
                university_id=30,
                program_id=200,
                stage=stage,
                created_days_ago=days_ago,
            )
        )
        next_id += 1

    return tuple(records)


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
        users=users + _demo_students(),
        countries=countries,
        universities=universities,
        programs=programs,
        applications=_applications(),
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
