"""Tests for ``POST /applications/{id}/stage`` (E25; Journey J18; issue #169).

Exercises the advance-stage API's full surface:

* Happy path: valid forward transition writes a new ``Application.stage``
  and one ``StageHistory`` row, returns both via ``AdvanceStageResponse``.
* Validation: invalid / undefined transitions return 422 and write NO
  history row.
* Terminal-stage source: applications already at ``enrolled`` /
  ``rejected`` / ``withdrawn`` reject further advances (422).
* Reasons: REJECTED / WITHDRAWN require a non-empty ``reason``; forward
  transitions and ENROLLED accept an optional reason; ``reason`` round-
  trips on the history entry returned in the response.
* Tenant scoping: cross-tenant access surfaces 404 (never 403) for both
  counselors and consultancy owners.
* Branch scoping: counselors cannot advance an application belonging to
  a different branch of their tenant (403).
* Permissions: STUDENT lacks ``application:advance_stage`` (403); missing
  JWT returns 401.
* Operational errors surface as 503.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.main import app
from app.models.application import Application
from app.models.stage_history import StageHistory
from app.models.tenant import Tenant
from app.models.user import User
from app.pipeline.default_transitions import seed_default_stage_transitions
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _create_tenant(db_session: Session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _seed_stage_rules(db_session: Session) -> None:
    """Populate the platform-default stage_transitions rule table."""
    seed_default_stage_transitions(db_session)


def _as_counselor(user: User) -> object:
    return make_authenticated_user(
        Role.COUNSELOR,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


def _as_branch_manager(user: User) -> object:
    return make_authenticated_user(
        Role.BRANCH_MANAGER,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


def _as_consultancy_owner(user: User) -> object:
    return make_authenticated_user(
        Role.CONSULTANCY_OWNER,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=None,
    )


def _as_student(user: User) -> object:
    return make_authenticated_user(
        Role.STUDENT,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_advance_stage_writes_history_for_valid_forward_transition(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Counselor advances a REGISTERED application to COUNSELING; history is logged."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["application"]["id"] == application.id
    assert body["application"]["stage"] == PipelineStage.COUNSELING.value

    # History row captured from the application's pre-update stage.
    entry = body["history_entry"]
    assert entry["application_id"] == application.id
    assert entry["from_stage"] == PipelineStage.REGISTERED.value
    assert entry["to_stage"] == PipelineStage.COUNSELING.value
    assert entry["changed_by_user_id"] == counselor.id
    assert entry["reason"] is None
    assert "changed_at" in entry
    assert "id" in entry

    # Verify the application row was updated and a StageHistory row was inserted.
    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == PipelineStage.COUNSELING
    history_rows = (
        db_session.query(StageHistory)
        .filter(StageHistory.application_id == application.id)
        .all()
    )
    assert len(history_rows) == 1
    assert history_rows[0].from_stage == PipelineStage.REGISTERED
    assert history_rows[0].to_stage == PipelineStage.COUNSELING
    assert history_rows[0].changed_by_user_id == counselor.id


def test_advance_stage_full_progression_lands_on_enrolled(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Walking the entire happy path REGISTERED → ... → ENROLLED works."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor))

    forward_chain = [
        PipelineStage.COUNSELING,
        PipelineStage.UNIVERSITY_SHORTLISTING,
        PipelineStage.APPLICATION_SUBMITTED,
        PipelineStage.DOCUMENT_VERIFICATION,
        PipelineStage.OFFER_LETTER,
        PipelineStage.VISA_PROCESSING,
        PipelineStage.ENROLLED,
    ]
    previous_stage = PipelineStage.REGISTERED
    for next_stage in forward_chain:
        response = client.post(
            f"/applications/{application.id}/stage",
            json={"to_stage": next_stage.value},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["application"]["stage"] == next_stage.value
        assert body["history_entry"]["from_stage"] == previous_stage.value
        assert body["history_entry"]["to_stage"] == next_stage.value
        previous_stage = next_stage

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == PipelineStage.ENROLLED


def test_advance_stage_consultancy_owner_can_advance_across_branches(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Consultancy Owners can advance applications from any branch in their tenant."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch_other = seed_branch(db_session, tenant_id=tenant.id, name="Branch B", city="Pune")
    owner = make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        tenant_id=tenant.id,
        branch_id=None,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_other.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_consultancy_owner(owner))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["application"]["stage"] == PipelineStage.COUNSELING.value


def test_advance_stage_branch_manager_can_advance_in_own_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Branch Manager in the application's branch can advance it."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_branch_manager(manager))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["application"]["stage"] == PipelineStage.COUNSELING.value


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_advance_stage_invalid_transition_returns_422_and_no_history(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """An undefined transition (e.g. REGISTERED → DOCUMENT_VERIFICATION) returns 422 and writes nothing."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.DOCUMENT_VERIFICATION.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "not allowed" in detail

    # No history row written, application.stage unchanged.
    db_session.expire_all()
    history_count = (
        db_session.query(StageHistory)
        .filter(StageHistory.application_id == application.id)
        .count()
    )
    assert history_count == 0
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == PipelineStage.REGISTERED


def test_advance_stage_backward_transition_rejected(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Backward moves (e.g. COUNSELING → REGISTERED) are invalid."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.REGISTERED.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "terminal_stage",
    [PipelineStage.ENROLLED, PipelineStage.REJECTED, PipelineStage.WITHDRAWN],
)
def test_advance_stage_terminal_source_rejects_further_advances(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    terminal_stage: PipelineStage,
) -> None:
    """Once an application is ENROLLED / REJECTED / WITHDRAWN, no further advances are allowed."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=terminal_stage,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == terminal_stage


def test_advance_stage_missing_to_stage_returns_422(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The request schema enforces ``to_stage`` as required."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_advance_stage_unknown_to_stage_returns_422(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """An unrecognized stage string is rejected at the schema boundary."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": "not_a_real_stage"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Reason-on-terminal tests (Requirements §5)
# ---------------------------------------------------------------------------


def test_advance_stage_to_rejected_requires_reason(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Transitioning to REJECTED without a reason returns 422 (Requirements §5)."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.REJECTED.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    # No history row written.
    db_session.expire_all()
    assert (
        db_session.query(StageHistory)
        .filter(StageHistory.application_id == application.id)
        .count()
    ) == 0


def test_advance_stage_to_withdrawn_requires_reason(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Transitioning to WITHDRAWN without a reason returns 422 (Requirements §5)."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.WITHDRAWN.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_advance_stage_to_rejected_with_reason_persists_reason(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A non-empty ``reason`` lets REJECTED transition through and is persisted."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={
            "to_stage": PipelineStage.REJECTED.value,
            "reason": "Student did not meet academic requirements",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["application"]["stage"] == PipelineStage.REJECTED.value
    assert body["history_entry"]["reason"] == "Student did not meet academic requirements"

    db_session.expire_all()
    history_rows = (
        db_session.query(StageHistory)
        .filter(StageHistory.application_id == application.id)
        .all()
    )
    assert len(history_rows) == 1
    assert history_rows[0].reason == "Student did not meet academic requirements"


def test_advance_stage_to_withdrawn_with_reason_persists_reason(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A non-empty ``reason`` lets WITHDRAWN transition through and is persisted."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.VISA_PROCESSING,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={
            "to_stage": PipelineStage.WITHDRAWN.value,
            "reason": "Student chose a different consultancy",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["history_entry"]["reason"] == "Student chose a different consultancy"


def test_advance_stage_forward_transition_accepts_optional_reason(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Forward transitions (e.g. COUNSELING → UNIVERSITY_SHORTLISTING) accept an optional reason."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={
            "to_stage": PipelineStage.UNIVERSITY_SHORTLISTING.value,
            "reason": "Ready to start the shortlist",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["history_entry"]["reason"] == "Ready to start the shortlist"


def test_advance_stage_to_rejected_with_whitespace_only_reason_is_rejected(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A whitespace-only ``reason`` is treated as missing for terminal-rejection targets."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.REJECTED.value, "reason": "   "},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tenant / branch / permission scoping
# ---------------------------------------------------------------------------


def test_advance_stage_returns_404_for_cross_tenant_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor in tenant A cannot advance an application belonging to tenant B (404, not 403)."""
    _seed_stage_rules(db_session)
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    counselor_b = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
    )
    application_a = seed_application(
        db_session,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor_b))

    response = client.post(
        f"/applications/{application_a.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_advance_stage_returns_404_for_cross_tenant_owner(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A consultancy owner in tenant A cannot advance an application belonging to tenant B (404, not 403)."""
    _seed_stage_rules(db_session)
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    owner_b = make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        tenant_id=tenant_b.id,
        branch_id=None,
    )
    application_a = seed_application(
        db_session,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_consultancy_owner(owner_b))

    response = client.post(
        f"/applications/{application_a.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_advance_stage_returns_404_for_missing_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A request for a non-existent application id surfaces 404."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    override_authenticated_user(_as_counselor(counselor))

    response = client.post(
        "/applications/999999/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_advance_stage_counselor_cannot_advance_application_in_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor in branch A cannot advance an application belonging to branch B (403)."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="Branch B", city="Pune")
    counselor_a = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch_a.id,
    )
    application_in_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor_a))

    response = client.post(
        f"/applications/{application_in_b.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_advance_stage_branch_manager_cannot_advance_application_in_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A branch manager in branch A cannot advance an application belonging to branch B (403)."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="Branch B", city="Pune")
    manager_a = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        tenant_id=tenant.id,
        branch_id=branch_a.id,
    )
    application_in_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_branch_manager(manager_a))

    response = client.post(
        f"/applications/{application_in_b.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_advance_stage_rejects_student_role(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A STUDENT lacks the ``application:advance_stage`` permission (403)."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_student(student))

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_advance_stage_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    """Without a Bearer token the endpoint returns 401."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        stage=PipelineStage.REGISTERED,
    )

    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Operational-error coverage
# ---------------------------------------------------------------------------


def test_advance_stage_returns_503_when_application_lookup_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError on ``db.get(Application, ...)`` surfaces as 503."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor))

    mock_session = MagicMock()
    mock_session.get.side_effect = OperationalError(
        "stmt", {}, Exception("no such table")
    )

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            f"/applications/{application.id}/stage",
            json={"to_stage": PipelineStage.COUNSELING.value},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Application service is temporarily unavailable"


def test_advance_stage_returns_503_when_commit_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError on the final ``db.commit()`` is caught and surfaces as 503."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor))

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

        def scalars(self, *args, **kwargs):
            return self._real.scalars(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    def override_get_db():
        yield _FlakyCommitSession(real_session)

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            f"/applications/{application.id}/stage",
            json={"to_stage": PipelineStage.COUNSELING.value},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_advance_stage_history_changed_at_is_close_to_now(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The recorded ``changed_at`` matches the wall-clock at the time of the request."""
    _seed_stage_rules(db_session)
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as_counselor(counselor))

    before = datetime.utcnow()
    response = client.post(
        f"/applications/{application.id}/stage",
        json={"to_stage": PipelineStage.COUNSELING.value},
        headers={"Authorization": "Bearer test-token"},
    )
    after = datetime.utcnow()

    assert response.status_code == 200
    entry = response.json()["history_entry"]
    parsed = datetime.fromisoformat(entry["changed_at"].replace("Z", "+00:00"))
    parsed_naive = parsed.replace(tzinfo=None)
    assert before <= parsed_naive <= after