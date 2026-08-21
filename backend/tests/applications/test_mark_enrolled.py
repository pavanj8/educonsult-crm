"""Tests for ``POST /applications/{id}/mark-enrolled`` (E38; Journey J31; #203).

Covers the dedicated mark-enrolled transition:

* happy path — a VISA_PROCESSING application is flipped to ENROLLED, the optional
  ``details`` are captured on the StageHistory row, and metadata is persisted;
* details are optional (a positive enrollment needs no mandatory reason);
* an application in a stage that cannot reach ENROLLED is 422 (left untouched);
* permission checks — only advance-stage roles may act; students are 403;
* tenant scoping (cross-tenant -> 404) and branch scoping (counselor in another
  branch -> 403).
"""

from __future__ import annotations

import pytest

from app.models.application import Application
from app.models.stage_history import StageHistory
from app.models.tenant import Tenant
from app.pipeline.default_transitions import seed_default_stage_transitions
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


def _create_tenant(db_session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _as(role: Role, user) -> object:
    return make_authenticated_user(
        role, user_id=user.id, tenant_id=user.tenant_id,
        branch_id=None if role in (Role.CONSULTANCY_OWNER, Role.SUPER_ADMIN) else user.branch_id,
    )


def _seed_enrollable_application(db_session, *, tenant, branch, counselor):
    return seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.VISA_PROCESSING,
    )


def test_mark_enrolled_flips_stage_and_captures_details(
    client, db_session, override_authenticated_user
):
    seed_default_stage_transitions(db_session)
    tenant = _create_tenant(db_session, name="Enrol Tenant", slug="enrol-tenant")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    application = _seed_enrollable_application(db_session, tenant=tenant, branch=branch, counselor=counselor)
    override_authenticated_user(_as(Role.COUNSELOR, counselor))

    response = client.post(
        f"/applications/{application.id}/mark-enrolled",
        json={"details": "Fall 2026 intake confirmed"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["application"]["stage"] == PipelineStage.ENROLLED.value
    entry = body["history_entry"]
    assert entry["from_stage"] == PipelineStage.VISA_PROCESSING.value
    assert entry["to_stage"] == PipelineStage.ENROLLED.value
    assert entry["changed_by_user_id"] == counselor.id
    assert entry["reason"] == "Fall 2026 intake confirmed"

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == PipelineStage.ENROLLED
    rows = db_session.query(StageHistory).filter(StageHistory.application_id == application.id).all()
    assert len(rows) == 1
    assert rows[0].reason == "Fall 2026 intake confirmed"


def test_mark_enrolled_details_are_optional(client, db_session, override_authenticated_user):
    seed_default_stage_transitions(db_session)
    tenant = _create_tenant(db_session, name="Enrol Opt", slug="enrol-opt")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    application = _seed_enrollable_application(db_session, tenant=tenant, branch=branch, counselor=counselor)
    override_authenticated_user(_as(Role.COUNSELOR, counselor))

    response = client.post(
        f"/applications/{application.id}/mark-enrolled",
        json={},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["history_entry"]["reason"] is None


def test_mark_enrolled_invalid_from_stage_is_422(client, db_session, override_authenticated_user):
    seed_default_stage_transitions(db_session)
    tenant = _create_tenant(db_session, name="Enrol Bad", slug="enrol-bad")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id,
        assigned_counselor_id=counselor.id, stage=PipelineStage.REGISTERED,
    )
    override_authenticated_user(_as(Role.COUNSELOR, counselor))

    response = client.post(
        f"/applications/{application.id}/mark-enrolled",
        json={"details": "too early"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 422, response.text
    db_session.expire_all()
    assert db_session.get(Application, application.id).stage == PipelineStage.REGISTERED


@pytest.mark.parametrize("role", [Role.STUDENT, Role.RECEPTIONIST, Role.VISA_PROCESSOR, Role.DOCUMENT_VERIFIER])
def test_mark_enrolled_denied_for_non_advance_roles(
    client, db_session, override_authenticated_user, role
):
    seed_default_stage_transitions(db_session)
    tenant = _create_tenant(db_session, name=f"Enrol {role.value}", slug=f"enrol-{role.value}")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    application = _seed_enrollable_application(db_session, tenant=tenant, branch=branch, counselor=counselor)
    caller = make_db_user(db_session, role, tenant_id=tenant.id, branch_id=branch.id)
    override_authenticated_user(_as(role, caller))

    response = client.post(
        f"/applications/{application.id}/mark-enrolled",
        json={"details": "x"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 403, response.text
    db_session.expire_all()
    assert db_session.get(Application, application.id).stage == PipelineStage.VISA_PROCESSING


def test_mark_enrolled_cross_tenant_is_404(client, db_session, override_authenticated_user):
    seed_default_stage_transitions(db_session)
    tenant = _create_tenant(db_session, name="Enrol Home", slug="enrol-home")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    application = _seed_enrollable_application(db_session, tenant=tenant, branch=branch, counselor=counselor)

    other = _create_tenant(db_session, name="Enrol Other", slug="enrol-other")
    other_branch = seed_branch(db_session, tenant_id=other.id)
    other_counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=other.id, branch_id=other_branch.id)
    override_authenticated_user(_as(Role.COUNSELOR, other_counselor))

    response = client.post(
        f"/applications/{application.id}/mark-enrolled",
        json={"details": "not mine"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 404, response.text


def test_mark_enrolled_counselor_other_branch_is_403(client, db_session, override_authenticated_user):
    seed_default_stage_transitions(db_session)
    tenant = _create_tenant(db_session, name="Enrol Branch", slug="enrol-branch")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="Branch B", city="Delhi")
    counselor_a = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id)
    application = _seed_enrollable_application(db_session, tenant=tenant, branch=branch_a, counselor=counselor_a)
    counselor_b = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id)
    override_authenticated_user(_as(Role.COUNSELOR, counselor_b))

    response = client.post(
        f"/applications/{application.id}/mark-enrolled",
        json={"details": "wrong branch"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 403, response.text
