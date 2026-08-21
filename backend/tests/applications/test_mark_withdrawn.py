"""Tests for ``POST /applications/{id}/mark-withdrawn`` (E40; Journey J33; #207).

Covers the dedicated mark-withdrawn transition:

* happy path — an in-flight application is flipped to WITHDRAWN and the REQUIRED
  reason is captured (trimmed) on the StageHistory row;
* reason is mandatory — missing / empty / whitespace-only is a 422;
* an application already in a terminal stage cannot be withdrawn (422);
* permission checks — only advance-stage roles may act; students are 403;
* tenant scoping (cross-tenant -> 404) and branch scoping (other branch -> 403).
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


def _seed_app(db_session, *, tenant, branch, counselor, stage=PipelineStage.DOCUMENT_VERIFICATION):
    return seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id,
        assigned_counselor_id=counselor.id, stage=stage,
    )


def _setup(db_session, slug):
    seed_default_stage_transitions(db_session)
    tenant = _create_tenant(db_session, name=slug, slug=slug)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    return tenant, branch, counselor


def test_mark_withdrawn_flips_stage_and_captures_reason(client, db_session, override_authenticated_user):
    tenant, branch, counselor = _setup(db_session, "wd-ok")
    application = _seed_app(db_session, tenant=tenant, branch=branch, counselor=counselor)
    override_authenticated_user(_as(Role.COUNSELOR, counselor))

    response = client.post(
        f"/applications/{application.id}/mark-withdrawn",
        json={"reason": "  Documents did not meet requirements  "},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["application"]["stage"] == PipelineStage.WITHDRAWN.value
    assert body["history_entry"]["to_stage"] == PipelineStage.WITHDRAWN.value
    assert body["history_entry"]["reason"] == "Documents did not meet requirements"  # trimmed

    db_session.expire_all()
    assert db_session.get(Application, application.id).stage == PipelineStage.WITHDRAWN
    rows = db_session.query(StageHistory).filter(StageHistory.application_id == application.id).all()
    assert rows[0].reason == "Documents did not meet requirements"


def test_mark_withdrawn_requires_a_reason(client, db_session, override_authenticated_user):
    tenant, branch, counselor = _setup(db_session, "wd-req")
    application = _seed_app(db_session, tenant=tenant, branch=branch, counselor=counselor)
    override_authenticated_user(_as(Role.COUNSELOR, counselor))
    url = f"/applications/{application.id}/mark-withdrawn"
    headers = {"Authorization": "Bearer test-token"}

    assert client.post(url, json={}, headers=headers).status_code == 422
    assert client.post(url, json={"reason": "   "}, headers=headers).status_code == 422
    assert client.post(url, json={"reason": "x" * 2001}, headers=headers).status_code == 422


def test_mark_withdrawn_terminal_stage_is_422(client, db_session, override_authenticated_user):
    tenant, branch, counselor = _setup(db_session, "wd-terminal")
    application = _seed_app(db_session, tenant=tenant, branch=branch, counselor=counselor, stage=PipelineStage.ENROLLED)
    override_authenticated_user(_as(Role.COUNSELOR, counselor))

    response = client.post(
        f"/applications/{application.id}/mark-withdrawn",
        json={"reason": "too late"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 422, response.text
    db_session.expire_all()
    assert db_session.get(Application, application.id).stage == PipelineStage.ENROLLED


@pytest.mark.parametrize("role", [Role.STUDENT, Role.RECEPTIONIST, Role.VISA_PROCESSOR, Role.DOCUMENT_VERIFIER])
def test_mark_withdrawn_denied_for_non_advance_roles(client, db_session, override_authenticated_user, role):
    tenant, branch, counselor = _setup(db_session, f"wd-authz-{role.value}")
    application = _seed_app(db_session, tenant=tenant, branch=branch, counselor=counselor)
    caller = make_db_user(db_session, role, tenant_id=tenant.id, branch_id=branch.id)
    override_authenticated_user(_as(role, caller))

    response = client.post(
        f"/applications/{application.id}/mark-withdrawn",
        json={"reason": "trying"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 403, response.text


def test_mark_withdrawn_cross_tenant_is_404(client, db_session, override_authenticated_user):
    tenant, branch, counselor = _setup(db_session, "wd-home")
    application = _seed_app(db_session, tenant=tenant, branch=branch, counselor=counselor)
    other = _create_tenant(db_session, name="wd-other", slug="wd-other")
    other_branch = seed_branch(db_session, tenant_id=other.id)
    other_counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=other.id, branch_id=other_branch.id)
    override_authenticated_user(_as(Role.COUNSELOR, other_counselor))

    response = client.post(
        f"/applications/{application.id}/mark-withdrawn",
        json={"reason": "not mine"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 404, response.text


def test_mark_withdrawn_counselor_other_branch_is_403(client, db_session, override_authenticated_user):
    seed_default_stage_transitions(db_session)
    tenant = _create_tenant(db_session, name="wd-branch", slug="wd-branch")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="Branch B", city="Delhi")
    counselor_a = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id)
    application = _seed_app(db_session, tenant=tenant, branch=branch_a, counselor=counselor_a)
    counselor_b = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id)
    override_authenticated_user(_as(Role.COUNSELOR, counselor_b))

    response = client.post(
        f"/applications/{application.id}/mark-withdrawn",
        json={"reason": "wrong branch"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 403, response.text
