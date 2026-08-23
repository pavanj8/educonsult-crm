"""Tests for the /meetings schedule/list/update endpoints (E22; Journey J15).

Covers:

* POST /meetings (schedule)
  - 201 happy path: counselor, branch manager, consultancy owner
  - 404 cross-tenant application
  - 403 cross-branch for counselor + branch manager (regression on
    iteration #1 finding from the Security Analyst)
  - 403 counselor scheduling for another counselor
  - 422 student mismatch / counselor missing / counselor wrong role
  - 422 validation errors (duration < 15, > 480, negative ids)
  - 409 when application has no assigned counselor
  - 401 missing auth
  - 503 on OperationalError
* GET /meetings (list)
  - counselor only sees own
  - branch manager sees branch-scoped
  - consultancy owner sees all in tenant
  - student sees only their own meetings (regression on iteration #1
    Security Analyst finding: students must NOT list every meeting in
    the tenant)
  - cross-tenant returns empty
  - filter by application_id / student_id
* PATCH /meetings/{id} (update)
  - 200 happy path (single-field, multi-field)
  - 404 missing / cross-tenant
  - 403 cross-branch for BM (regression on iteration #1 finding)
  - 403 cross-counselor for counselor
  - 422 validation errors
  - 401 missing auth
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.main import app
from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.counseling.helpers import seed_meeting
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _create_tenant(db_session: Session, *, name: str = "EduConsult Test", slug: str = "educonsult") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _auth_for(user) -> object:
    return make_authenticated_user(
        user.role,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


def _auth_consultancy_owner(user) -> object:
    return make_authenticated_user(
        Role.CONSULTANCY_OWNER,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=None,
    )


def _schedule_payload(
    *,
    application_id: int,
    student_id: int,
    counselor_id: int,
    duration_minutes: int = 30,
    location: str | None = "Room 1",
    notes: str | None = None,
) -> dict:
    return {
        "application_id": application_id,
        "student_id": student_id,
        "counselor_id": counselor_id,
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "duration_minutes": duration_minutes,
        "location": location,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# POST /meetings -- happy paths
# ---------------------------------------------------------------------------


def test_counselor_schedules_meeting_for_assigned_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["application_id"] == application.id
    assert body["student_id"] == student.id
    assert body["counselor_id"] == counselor.id
    assert body["tenant_id"] == tenant.id
    assert body["duration_minutes"] == 30
    assert body["location"] == "Room 1"


def test_branch_manager_schedules_meeting_in_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["counselor_id"] == counselor.id


def test_consultancy_owner_schedules_meeting(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text


def test_counselor_schedules_with_default_duration(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Pydantic ``MeetingCreate`` defaults ``duration_minutes`` to 60."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    payload = _schedule_payload(
        application_id=application.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )
    payload.pop("duration_minutes")

    response = client.post(
        "/meetings",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["duration_minutes"] == 60


# ---------------------------------------------------------------------------
# POST /meetings -- tenant + branch scoping
# ---------------------------------------------------------------------------


def test_schedule_returns_404_for_cross_tenant_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor in tenant A cannot schedule against an application in tenant B (404)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    application_b = seed_application(
        db_session,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_b))

    # Now make a counselor A and try to access application B.
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application_b.id,
            student_id=student_b.id,
            counselor_id=counselor_b.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_schedule_returns_404_for_missing_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=999999,
            student_id=student.id,
            counselor_id=counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_counselor_cannot_schedule_for_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor in branch A cannot schedule against an application in branch B (403)."""
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    application_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application_b.id,
            student_id=student_b.id,
            counselor_id=counselor_b.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_branch_manager_cannot_schedule_for_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A branch manager in branch A cannot schedule against an application in branch B (403)."""
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    application_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application_b.id,
            student_id=student_b.id,
            counselor_id=counselor_b.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_counselor_cannot_schedule_for_unassigned_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor cannot schedule a meeting on an application they're not assigned to (403)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    other_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=other_counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Meeting is not assigned to this counselor"


def test_counselor_schedule_returns_409_when_application_has_no_assigned_counselor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """An application with ``assigned_counselor_id IS NULL`` must surface as 409, not a misleading 403."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Application has no assigned counselor; cannot schedule meeting"
    )


def test_counselor_cannot_schedule_for_another_counselor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor cannot put a different counselor's id on a meeting they schedule (403)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    other_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=other_counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Counselors may only schedule their own meetings"


# ---------------------------------------------------------------------------
# POST /meetings -- payload validation
# ---------------------------------------------------------------------------


def test_schedule_rejects_student_mismatch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A different ``student_id`` than the application's student surfaces as 422."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    other_student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=other_student.id,
            counselor_id=counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Student is not the application's student"


def test_schedule_rejects_missing_counselor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A branch manager scheduling for an unknown counselor surfaces as 422.

    Counselors are short-circuited before this validation: they can only
    schedule meetings for themselves (403), so we exercise this path via
    a branch manager who is allowed to pick any counselor in their
    branch.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=999999,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Counselor not found"


def test_schedule_rejects_counselor_with_wrong_role(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A branch manager picking a non-COUNSELOR user surfaces as 422."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    other = make_db_user(
        db_session, Role.RECEPTIONIST, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=other.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Counselor not found"


def test_schedule_rejects_counselor_from_other_branch_for_branch_manager(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A branch manager cannot pick a counselor from a different branch (422)."""
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_a.id
    )
    application_a = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_a.id,
        student_id=student_a.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application_a.id,
            student_id=student_a.id,
            counselor_id=counselor_b.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Counselor not found"


def test_schedule_rejects_duration_too_short(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=counselor.id,
            duration_minutes=10,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_schedule_rejects_duration_too_long(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=counselor.id,
            duration_minutes=500,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_schedule_rejects_zero_application_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """``application_id=0`` fails the Pydantic ``gt=0`` check (422)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=0,
            student_id=student.id,
            counselor_id=counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /meetings -- auth + 503
# ---------------------------------------------------------------------------


def test_schedule_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post("/meetings", json={})

    assert response.status_code == 401


@pytest.mark.parametrize(
    "actor_role",
    [Role.STUDENT, Role.RECEPTIONIST, Role.DOCUMENT_VERIFIER, Role.VISA_PROCESSOR],
)
def test_schedule_rejects_roles_without_meeting_schedule_permission(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    actor_role: Role,
) -> None:
    """Roles without ``MEETING_SCHEDULE`` are rejected (403)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    actor = make_db_user(
        db_session, actor_role, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(actor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=1,
            student_id=2,
            counselor_id=3,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_schedule_returns_503_when_commit_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    real_session = db_session

    class _FlakyCommitSession:
        def __init__(self, real):
            self._real = real

        def get(self, *args, **kwargs):
            return self._real.get(*args, **kwargs)

        def commit(self, *args, **kwargs):
            raise OperationalError("stmt", {}, Exception("disk full"))

        def add(self, *args, **kwargs):
            return self._real.add(*args, **kwargs)

        def refresh(self, *args, **kwargs):
            return self._real.refresh(*args, **kwargs)

        def rollback(self, *args, **kwargs):
            return self._real.rollback(*args, **kwargs)

        def execute(self, *args, **kwargs):
            return self._real.execute(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    def override_get_db():
        yield _FlakyCommitSession(real_session)

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/meetings",
            json=_schedule_payload(
                application_id=application.id,
                student_id=student.id,
                counselor_id=counselor.id,
            ),
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Meeting service is temporarily unavailable"


# ---------------------------------------------------------------------------
# GET /meetings -- scoping
# ---------------------------------------------------------------------------


def test_counselor_list_returns_only_own_meetings(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor sees only meetings where they are the named counselor."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    other = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    app_me = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    app_other = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=other.id,
    )
    mine = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=app_me.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )
    not_mine = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=app_other.id,
        student_id=student.id,
        counselor_id=other.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.get(
        "/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    ids = {item["id"] for item in body}
    assert ids == {mine.id}
    assert not_mine.id not in ids


def test_branch_manager_list_returns_branch_scoped_meetings(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A branch manager sees meetings whose application lives in their branch only."""
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_a.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    application_a = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_a.id,
        student_id=student_a.id,
        assigned_counselor_id=counselor_a.id,
    )
    application_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    meeting_in_a = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application_a.id,
        student_id=student_a.id,
        counselor_id=counselor_a.id,
    )
    meeting_in_b = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application_b.id,
        student_id=student_b.id,
        counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.get(
        "/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {meeting_in_a.id}
    assert meeting_in_b.id not in ids


def test_consultancy_owner_list_returns_all_in_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A consultancy owner sees meetings across both branches of their tenant."""
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_a.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    application_a = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_a.id,
        student_id=student_a.id,
        assigned_counselor_id=counselor_a.id,
    )
    application_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    meeting_a = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application_a.id,
        student_id=student_a.id,
        counselor_id=counselor_a.id,
    )
    meeting_b = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application_b.id,
        student_id=student_b.id,
        counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.get(
        "/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {meeting_a.id, meeting_b.id}


def test_student_list_returns_only_own_meetings(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student must only see meetings where they are the named student.

    Regression test for iteration #1 Security Analyst finding: students
    must NOT be able to list every meeting in the tenant, only their own.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    other_student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application_me = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    application_other = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=other_student.id,
        assigned_counselor_id=counselor.id,
    )
    mine = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application_me.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )
    not_mine = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application_other.id,
        student_id=other_student.id,
        counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(student))

    response = client.get(
        "/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {mine.id}
    assert not_mine.id not in ids


def test_list_excludes_cross_tenant_meetings(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor in tenant A does not see meetings from tenant B (empty list, not error)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    application_b = seed_application(
        db_session,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    seed_meeting(
        db_session,
        tenant_id=tenant_b.id,
        application_id=application_b.id,
        student_id=student_b.id,
        counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.get(
        "/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_filters_by_application_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    app_one = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    app_two = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting_one = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=app_one.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )
    seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=app_two.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.get(
        f"/meetings?application_id={app_one.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {meeting_one.id}


def test_list_filters_by_student_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    app_a = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student_a.id,
        assigned_counselor_id=counselor.id,
    )
    app_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor.id,
    )
    meeting_a = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=app_a.id,
        student_id=student_a.id,
        counselor_id=counselor.id,
    )
    seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=app_b.id,
        student_id=student_b.id,
        counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.get(
        f"/meetings?student_id={student_a.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {meeting_a.id}


def test_list_rejects_zero_application_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.get(
        "/meetings?application_id=0",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_list_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.get("/meetings")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /meetings/{id} -- happy paths + scoping
# ---------------------------------------------------------------------------


def test_counselor_updates_own_meeting(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.patch(
        f"/meetings/{meeting.id}",
        json={"duration_minutes": 90, "notes": "Bring documents"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["duration_minutes"] == 90
    assert body["notes"] == "Bring documents"
    assert body["location"] == meeting.location  # left untouched (exclude_unset)


def test_branch_manager_updates_meeting_in_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/meetings/{meeting.id}",
        json={"location": "Room 5"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["location"] == "Room 5"


def test_update_returns_404_for_missing_meeting(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.patch(
        "/meetings/999999",
        json={"duration_minutes": 90},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_update_returns_404_for_cross_tenant_meeting(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor in tenant A cannot update a meeting in tenant B (404, not 403)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    application_b = seed_application(
        db_session,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    meeting_b = seed_meeting(
        db_session,
        tenant_id=tenant_b.id,
        application_id=application_b.id,
        student_id=student_b.id,
        counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.patch(
        f"/meetings/{meeting_b.id}",
        json={"duration_minutes": 90},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_branch_manager_cannot_update_meeting_in_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A branch manager in branch A cannot update a meeting in branch B (403).

    Regression test for iteration #1 Security Analyst finding: _load_meeting
    must enforce branch scope for Branch Manager just as _load_application
    does.
    """
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    application_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    meeting_b = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application_b.id,
        student_id=student_b.id,
        counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.patch(
        f"/meetings/{meeting_b.id}",
        json={"duration_minutes": 90},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_counselor_cannot_update_other_counselors_meeting(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    other = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=other.id,
    )
    meeting = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=student.id,
        counselor_id=other.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.patch(
        f"/meetings/{meeting.id}",
        json={"duration_minutes": 90},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Meeting is not assigned to this counselor"


def test_student_cannot_update_meeting(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student has MEETING_READ but not MEETING_SCHEDULE; updates are 403."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(student))

    response = client.patch(
        f"/meetings/{meeting.id}",
        json={"duration_minutes": 90},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_update_rejects_invalid_duration(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.patch(
        f"/meetings/{meeting.id}",
        json={"duration_minutes": 5},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_update_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.patch("/meetings/1", json={})
    assert response.status_code == 401


def test_update_with_empty_payload_returns_meeting_unchanged(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """An empty PATCH body is a no-op (exclude_unset)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=student.id,
        counselor_id=counselor.id,
        duration_minutes=45,
        notes="original",
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.patch(
        f"/meetings/{meeting.id}",
        json={},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["duration_minutes"] == 45
    assert body["notes"] == "original"


# ---------------------------------------------------------------------------
# E23 / Journey J16: meeting creation must trigger a student notification.
# Regression test for issue #163 ("Wire meeting creation into notification
# trigger"). Without the wiring, ``POST /meetings`` persists the Meeting
# row but no Notification row is written, and the student never learns
# about the meeting through the in-app notification center.
# ---------------------------------------------------------------------------


def test_schedule_meeting_creates_notification_for_student(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=counselor.id,
            location="Room 1",
        ),
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 201, response.text

    # The student gets exactly one in-app notification for the newly
    # scheduled meeting. The counselor (the actor) is not self-notified.
    from app.models.notification import Notification

    student_rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .all()
    )
    assert len(student_rows) == 1
    assert student_rows[0].title == "Meeting scheduled"
    assert "Room 1" in student_rows[0].message

    counselor_rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == counselor.id)
        .all()
    )
    assert counselor_rows == []


def test_schedule_meeting_notification_carries_meeting_time(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The notification body contains the scheduled time (UTC) so the student
    can see when the meeting is without opening the full meeting view."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/meetings",
        json=_schedule_payload(
            application_id=application.id,
            student_id=student.id,
            counselor_id=counselor.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 201, response.text

    from app.models.notification import Notification

    row = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .one()
    )
    assert "UTC" in row.message


def test_schedule_meeting_notification_failure_does_not_break_meeting_creation(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A flaky notification write must not surface as a 5xx on meeting creation
    (J16 / E23 + E48 contract: notification helpers are no-throw wrappers)."""
    from app.db.database import get_db
    from app.main import app
    from app.models.notification import Notification
    from sqlalchemy.exc import OperationalError

    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    real_session = db_session

    # Count how many times the router calls commit() so we can
    # selectively fail the *second* commit (the one that follows
    # notify_meeting_scheduled) without breaking the meeting insert.
    state = {"commit_count": 0}

    class _FlakySecondCommitSession:
        def __init__(self, real):
            self._real = real

        def commit(self, *args, **kwargs):
            state["commit_count"] += 1
            if state["commit_count"] == 2:
                raise OperationalError("stmt", {}, Exception("disk full"))
            return self._real.commit(*args, **kwargs)

        def rollback(self, *args, **kwargs):
            return self._real.rollback(*args, **kwargs)

        def add(self, *args, **kwargs):
            return self._real.add(*args, **kwargs)

        def flush(self, *args, **kwargs):
            return self._real.flush(*args, **kwargs)

        def refresh(self, *args, **kwargs):
            return self._real.refresh(*args, **kwargs)

        def execute(self, *args, **kwargs):
            return self._real.execute(*args, **kwargs)

        def get(self, *args, **kwargs):
            return self._real.get(*args, **kwargs)

        def scalars(self, *args, **kwargs):
            return self._real.scalars(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    def override_get_db():
        yield _FlakySecondCommitSession(real_session)

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/meetings",
            json=_schedule_payload(
                application_id=application.id,
                student_id=student.id,
                counselor_id=counselor.id,
            ),
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    # The meeting itself was created (first commit succeeded); the
    # notification write failed (second commit failed) but the route
    # swallows that, so the response is still 201.
    assert response.status_code == 201, response.text

    # The student did NOT get a notification row (the second commit
    # rolled back the failed notification insert).
    rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .all()
    )
    assert rows == []
    # But the meeting IS in the database.
    from app.models.meeting import Meeting

    assert (
        db_session.query(Meeting)
        .filter(Meeting.application_id == application.id)
        .count()
        == 1
    )
