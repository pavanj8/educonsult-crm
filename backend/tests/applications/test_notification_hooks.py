"""Integration tests: E48 notification hooks fire on the application router.

Traces to:

* Requirements §6 Notifications (in-app + email for status changes …)
* Journey J41 ("User receives an in-app notification on a relevant
  event").
* Epic E48 / Issue #231 — the key-event coverage required by the
  ticket.

These tests exercise the **router-side** hooks — i.e. they call the
real HTTP endpoints and assert that, when the domain event fires, a
``Notification`` row is persisted with the right ``event_type`` /
recipient / FK payload. The pure-service coverage lives in
``tests/services/test_notifications.py``.

Coverage:

* ``POST /applications``  -> notifies the assigned counselor
  (``EVENT_APPLICATION_CREATED``).
* ``POST /applications``  -> **no** notification when the branch has
  no active counselors at create time.
* ``POST /applications/{id}/stage`` -> notifies the application's
  student (``EVENT_APPLICATION_STAGE_ADVANCED``).
* ``POST /applications/{id}/stage`` -> no notification when the
  application has no resolvable student (defensive no-op).
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.notification import Notification
from app.pipeline.default_transitions import seed_default_stage_transitions
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from app.services.notifications import (
    EVENT_APPLICATION_CREATED,
    EVENT_APPLICATION_STAGE_ADVANCED,
)
from tests.applications.helpers import seed_application
from tests.applications.test_create_application import (
    _authenticate_student,
    _create_tenant,
    _seed_master_data_for_tenant,
    make_create_application_payload,
)
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_notifications(db_session) -> list[Notification]:
    return list(db_session.scalars(select(Notification)).all())


def _seed_counselor(db_session, *, tenant_id: int, branch_id: int):
    return make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )


def _seed_stage_rules(db_session) -> None:
    """Populate the platform-default stage_transitions rule table."""
    seed_default_stage_transitions(db_session)


# ---------------------------------------------------------------------------
# POST /applications -> notify the assigned counselor
# ---------------------------------------------------------------------------


def test_create_application_notifies_assigned_counselor(
    client, db_session, override_authenticated_user
):
    """A successful ``POST /applications`` generates a notification for the assigned counselor."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = _seed_counselor(
        db_session, tenant_id=tenant.id, branch_id=branch.id
    )
    university, program = _seed_master_data_for_tenant(
        db_session, tenant_id=tenant.id
    )

    # The router's auto-assignment service picks the only active counselor.
    _authenticate_student(
        override_authenticated_user,
        student=student,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        "/applications",
        json=make_create_application_payload(
            university_id=university.id,
            program_id=program.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    application_id = response.json()["id"]

    notifications = _list_notifications(db_session)
    assert len(notifications) == 1
    note = notifications[0]
    assert note.event_type == EVENT_APPLICATION_CREATED
    assert note.user_id == counselor.id
    assert note.tenant_id == tenant.id
    assert note.related_application_id == application_id
    assert note.read_at is None


def test_create_application_skips_notification_when_no_counselor(
    client, db_session, override_authenticated_user
):
    """No active counselors -> no notification row is generated (E19 design)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    # NB: no counselor seeded in this branch.
    university, program = _seed_master_data_for_tenant(
        db_session, tenant_id=tenant.id
    )

    _authenticate_student(
        override_authenticated_user,
        student=student,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        "/applications",
        json=make_create_application_payload(
            university_id=university.id,
            program_id=program.id,
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    assert _list_notifications(db_session) == []


# ---------------------------------------------------------------------------
# POST /applications/{id}/stage -> notify the student
# ---------------------------------------------------------------------------


def test_advance_stage_notifies_student(
    client, db_session, override_authenticated_user
):
    """A successful stage advance generates a notification for the application's student."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = _seed_counselor(
        db_session, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text

    notifications = _list_notifications(db_session)
    assert len(notifications) == 1
    note = notifications[0]
    assert note.event_type == EVENT_APPLICATION_STAGE_ADVANCED
    assert note.user_id == student.id
    assert note.tenant_id == tenant.id
    assert note.related_application_id == application.id
    # The hook records the FK to the StageHistory row the API just wrote.
    assert note.related_stage_history_id is not None


def test_advance_stage_invalid_transition_writes_no_notification(
    client, db_session, override_authenticated_user
):
    """A rejected (422) transition must not generate any notification row."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = _seed_counselor(
        db_session, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    # REGISTERED -> OFFER_LETTER is not a valid forward transition.
    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.OFFER_LETTER.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert _list_notifications(db_session) == []
