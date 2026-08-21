"""Unit tests for the round-robin counselor-assignment service (E19; J12; #150)."""

from __future__ import annotations

from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from app.services.counselor_assignment import assign_counselor_round_robin
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_db_user


def _tenant(db_session, slug) -> Tenant:
    tenant = Tenant(name=slug, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _assign_app(db_session, *, tenant, branch, counselor_id):
    return seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id,
        assigned_counselor_id=counselor_id, stage=PipelineStage.REGISTERED,
    )


def test_returns_none_when_branch_is_none(db_session):
    tenant = _tenant(db_session, "cra-none")
    assert assign_counselor_round_robin(db_session, tenant_id=tenant.id, branch_id=None) is None


def test_returns_none_when_no_active_counselors(db_session):
    tenant = _tenant(db_session, "cra-empty")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    # An inactive counselor and a non-counselor must be ignored.
    make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id, is_active=False)
    make_db_user(db_session, Role.RECEPTIONIST, tenant_id=tenant.id, branch_id=branch.id)
    assert assign_counselor_round_robin(db_session, tenant_id=tenant.id, branch_id=branch.id) is None


def test_single_counselor_is_always_chosen(db_session):
    tenant = _tenant(db_session, "cra-single")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    assert assign_counselor_round_robin(db_session, tenant_id=tenant.id, branch_id=branch.id) == counselor.id


def test_ties_break_on_lowest_id(db_session):
    tenant = _tenant(db_session, "cra-tie")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    a = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    b = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    assert assign_counselor_round_robin(db_session, tenant_id=tenant.id, branch_id=branch.id) == min(a.id, b.id)


def test_picks_least_loaded_counselor(db_session):
    tenant = _tenant(db_session, "cra-load")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    busy = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    idle = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    # Give `busy` two assignments; `idle` should win despite (possibly) higher id.
    _assign_app(db_session, tenant=tenant, branch=branch, counselor_id=busy.id)
    _assign_app(db_session, tenant=tenant, branch=branch, counselor_id=busy.id)
    assert assign_counselor_round_robin(db_session, tenant_id=tenant.id, branch_id=branch.id) == idle.id


def test_ignores_other_branch_and_other_tenant_counselors(db_session):
    tenant = _tenant(db_session, "cra-scope")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Delhi")
    only_in_b = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id)
    other_tenant = _tenant(db_session, "cra-other")
    other_branch = seed_branch(db_session, tenant_id=other_tenant.id)
    make_db_user(db_session, Role.COUNSELOR, tenant_id=other_tenant.id, branch_id=other_branch.id)

    # Branch A has no counselor -> None; branch B resolves only its own counselor.
    assert assign_counselor_round_robin(db_session, tenant_id=tenant.id, branch_id=branch_a.id) is None
    assert assign_counselor_round_robin(db_session, tenant_id=tenant.id, branch_id=branch_b.id) == only_in_b.id


def test_even_distribution_over_many_assignments(db_session):
    """Simulate the trigger: repeatedly pick + assign; loads stay within 1."""
    tenant = _tenant(db_session, "cra-even")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselors = [
        make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
        for _ in range(3)
    ]
    for _ in range(9):
        chosen = assign_counselor_round_robin(db_session, tenant_id=tenant.id, branch_id=branch.id)
        _assign_app(db_session, tenant=tenant, branch=branch, counselor_id=chosen)

    from app.models.application import Application

    counts = {}
    for c in counselors:
        counts[c.id] = (
            db_session.query(Application)
            .filter(Application.assigned_counselor_id == c.id)
            .count()
        )
    assert max(counts.values()) - min(counts.values()) <= 1
    assert sum(counts.values()) == 9
