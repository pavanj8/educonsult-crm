"""Terminal states (Enrolled / Rejected / Withdrawn) are final (E40; J31-J33; #209).

Once an application reaches a terminal stage no further stage transition is
allowed — neither the generic advance-stage endpoint nor any of the dedicated
mark-enrolled / mark-rejected / mark-withdrawn actions may move it — and the
application is left untouched (422, no history row for the rejected attempt).
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

TERMINAL_STAGES = [PipelineStage.ENROLLED, PipelineStage.REJECTED, PipelineStage.WITHDRAWN]


def _tenant(db_session, slug) -> Tenant:
    tenant = Tenant(name=slug, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _setup(db_session, slug, stage):
    seed_default_stage_transitions(db_session)
    tenant = _tenant(db_session, slug)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id,
        assigned_counselor_id=counselor.id, stage=stage,
    )
    override = make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=tenant.id, branch_id=branch.id)
    return application, override


def test_terminal_stages_are_marked_terminal():
    """The three outcome stages report as terminal; pipeline stages do not."""
    assert PipelineStage.terminal_stages() == set(TERMINAL_STAGES)
    for stage in TERMINAL_STAGES:
        assert stage.is_terminal
    assert not PipelineStage.VISA_PROCESSING.is_terminal


@pytest.mark.parametrize("stage", TERMINAL_STAGES)
@pytest.mark.parametrize(
    "path,body",
    [
        ("mark-enrolled", {"details": "x"}),
        ("mark-rejected", {"reason": "x"}),
        ("mark-withdrawn", {"reason": "x"}),
        ("stage", {"to_stage": PipelineStage.COUNSELING.value}),
    ],
)
def test_no_transition_out_of_a_terminal_stage(
    client, db_session, override_authenticated_user, stage, path, body
):
    application, override = _setup(db_session, f"term-{stage.value}-{path}", stage)
    override_authenticated_user(override)

    response = client.post(
        f"/applications/{application.id}/{path}",
        json=body,
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422, response.text
    db_session.expire_all()
    assert db_session.get(Application, application.id).stage == stage
    # No history row was written for the rejected transition attempt.
    assert (
        db_session.query(StageHistory)
        .filter(StageHistory.application_id == application.id)
        .count()
        == 0
    )


@pytest.mark.parametrize(
    "path,body,expected",
    [
        ("mark-enrolled", {"details": "done"}, PipelineStage.ENROLLED),
        ("mark-rejected", {"reason": "no"}, PipelineStage.REJECTED),
        ("mark-withdrawn", {"reason": "left"}, PipelineStage.WITHDRAWN),
    ],
)
def test_each_terminal_state_is_reachable(
    client, db_session, override_authenticated_user, path, body, expected
):
    """Each dedicated action reaches its own distinct terminal state from an
    in-flight application."""
    application, override = _setup(db_session, f"reach-{expected.value}", PipelineStage.VISA_PROCESSING)
    override_authenticated_user(override)

    response = client.post(
        f"/applications/{application.id}/{path}",
        json=body,
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["application"]["stage"] == expected.value
