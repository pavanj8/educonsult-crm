"""Tests for the ``GET /me/meetings`` self-service endpoint (E23; J16).

This endpoint backs the upcoming-meetings widget on the student
dashboard (frontend ticket #162). The contract is intentionally
narrower than the staff-side ``GET /meetings`` route:

* it is student-only -- any other role is rejected with 403
  regardless of what the caller asks for, so a counselor or staff
  token cannot use the ``/me`` prefix as a side door past the
  role-aware scoping of ``GET /meetings``;
* it is tenant-scoped: ``Meeting.tenant_id == current_user.tenant_id``;
* it is student-scoped: ``Meeting.student_id == current_user.id``.

The staff-side ``GET /meetings`` route already tests the
tenant + branch + role scoping for the wider matrix; the cases here
are specifically the regressions called out by the iteration #2
Test Engineer finding for the widget's backing endpoint:

(a) a student calling ``/me/meetings`` only receives meetings where
    ``student_id == current_user.id``;
(b) a counselor / staff calling the same endpoint does NOT receive
    any meetings (the endpoint is student-scoped);
(c) two students in the same tenant see disjoint result sets.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.counseling.helpers import seed_meeting
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Shared helpers (mirror the conventions in test_meetings.py).
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


def _seed_meeting_for(
    db_session: Session,
    *,
    tenant_id: int,
    student_id: int,
    counselor_id: int,
    branch_id: int,
    scheduled_offset_days: int = 1,
) -> int:
    """Create a meeting for the given student/counselor pair and return its id.

    A dedicated helper rather than reusing ``seed_meeting`` directly so
    each test reads as "seed a meeting for student X" without the
    long boilerplate of an ``Application`` factory call.
    """
    application = seed_application(
        db_session,
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_id=student_id,
        assigned_counselor_id=counselor_id,
    )
    scheduled_at = datetime.now(timezone.utc) + timedelta(days=scheduled_offset_days)
    meeting = seed_meeting(
        db_session,
        tenant_id=tenant_id,
        application_id=application.id,
        student_id=student_id,
        counselor_id=counselor_id,
        scheduled_at=scheduled_at,
    )
    return meeting.id


# ---------------------------------------------------------------------------
# Acceptance criterion (a) — student sees only their own meetings.
# ---------------------------------------------------------------------------


def test_student_sees_only_own_meetings_via_me_meetings(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student calling ``GET /me/meetings`` receives only their own meetings.

    Mirrors the existing ``test_student_list_returns_only_own_meetings``
    regression but exercised through the ``/me`` self-prefix so we have
    direct coverage of the widget's actual endpoint.
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

    mine_id = _seed_meeting_for(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        counselor_id=counselor.id,
        branch_id=branch.id,
    )
    not_mine_id = _seed_meeting_for(
        db_session,
        tenant_id=tenant.id,
        student_id=other_student.id,
        counselor_id=counselor.id,
        branch_id=branch.id,
    )
    override_authenticated_user(_auth_for(student))

    response = client.get(
        "/me/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    ids = {item["id"] for item in body}
    assert ids == {mine_id}
    assert not_mine_id not in ids


def test_me_meetings_returns_empty_list_when_student_has_no_meetings(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student with no meetings receives ``[]``, not a 404 (an empty state is a valid widget state)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(student))

    response = client.get(
        "/me/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_me_meetings_ordered_by_scheduled_at_ascending(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Results are returned in scheduled_at ascending order so the widget can render without re-sorting."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )

    # Insert deliberately out of order so the test would fail if the
    # endpoint forgot the ``order_by(scheduled_at)`` clause.
    later_id = _seed_meeting_for(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        counselor_id=counselor.id,
        branch_id=branch.id,
        scheduled_offset_days=7,
    )
    sooner_id = _seed_meeting_for(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        counselor_id=counselor.id,
        branch_id=branch.id,
        scheduled_offset_days=1,
    )
    override_authenticated_user(_auth_for(student))

    response = client.get(
        "/me/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()]
    assert ids == [sooner_id, later_id]


def test_me_meetings_includes_past_and_future(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The endpoint returns ALL the student's meetings (past + future).

    The widget filters to ``scheduled_at >= now`` client-side; the
    endpoint deliberately stays a thin list so the contract stays
    predictable and a future "meeting history" view can reuse it.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    past_id = _seed_meeting_for(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        counselor_id=counselor.id,
        branch_id=branch.id,
        scheduled_offset_days=-3,
    )
    future_id = _seed_meeting_for(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        counselor_id=counselor.id,
        branch_id=branch.id,
        scheduled_offset_days=2,
    )
    override_authenticated_user(_auth_for(student))

    response = client.get(
        "/me/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {past_id, future_id}


def test_me_meetings_isolates_cross_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student in tenant A receives no meetings from tenant B even if they somehow share a user id (defense-in-depth).

    The tenant scoping on ``Meeting.tenant_id`` makes cross-tenant
    leaks impossible without a deliberate bypass.
    """
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)

    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )

    # A meeting that exists only in tenant B's space.
    other_tenant_meeting_id = _seed_meeting_for(
        db_session,
        tenant_id=tenant_b.id,
        student_id=make_db_user(
            db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
        ).id,
        counselor_id=counselor_b.id,
        branch_id=branch_b.id,
    )
    override_authenticated_user(_auth_for(student_a))

    response = client.get(
        "/me/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert other_tenant_meeting_id not in ids
    assert ids == set()


# ---------------------------------------------------------------------------
# Acceptance criterion (b) — non-students are rejected.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role",
    [
        Role.COUNSELOR,
        Role.BRANCH_MANAGER,
        Role.CONSULTANCY_OWNER,
        Role.SUPER_ADMIN,
        Role.RECEPTIONIST,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
    ],
)
def test_non_student_calling_me_meetings_is_rejected(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    role: Role,
) -> None:
    """``/me/meetings`` is student-only; every other role gets 403."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    user = make_db_user(db_session, role, tenant_id=tenant.id, branch_id=branch.id)
    override_authenticated_user(_auth_for(user))

    response = client.get(
        "/me/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Only students can access this endpoint"


# ---------------------------------------------------------------------------
# Acceptance criterion (c) — two students in the same tenant see disjoint sets.
# ---------------------------------------------------------------------------


def test_two_students_same_tenant_see_disjoint_meetings(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Two students in the same tenant see disjoint meeting lists."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student_one = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    student_two = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )

    one_id = _seed_meeting_for(
        db_session,
        tenant_id=tenant.id,
        student_id=student_one.id,
        counselor_id=counselor.id,
        branch_id=branch.id,
    )
    two_id = _seed_meeting_for(
        db_session,
        tenant_id=tenant.id,
        student_id=student_two.id,
        counselor_id=counselor.id,
        branch_id=branch.id,
    )

    # First call as student_one.
    override_authenticated_user(_auth_for(student_one))
    response_one = client.get(
        "/me/meetings",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response_one.status_code == 200, response_one.text
    assert {item["id"] for item in response_one.json()} == {one_id}

    # Second call as student_two.
    override_authenticated_user(_auth_for(student_two))
    response_two = client.get(
        "/me/meetings",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response_two.status_code == 200, response_two.text
    assert {item["id"] for item in response_two.json()} == {two_id}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_me_meetings_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    """An unauthenticated request is rejected with 401."""
    response = client.get("/me/meetings")
    assert response.status_code == 401
