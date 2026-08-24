"""Issue #106 plan assignment and catalog API tests (E9, Journey J2)."""

from datetime import timedelta

import pytest

from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user


def _seed_catalog(db_session) -> list[Plan]:
    plans = [
        Plan(code=PlanTier.STARTER, name="Starter", max_branches=1, max_staff=3, max_students=50),
        Plan(code=PlanTier.GROWTH, name="Growth", max_branches=5, max_staff=10, max_students=200),
        Plan(code=PlanTier.ENTERPRISE, name="Enterprise", max_branches=None, max_staff=None, max_students=None),
    ]
    db_session.add_all(plans)
    db_session.commit()
    return plans


@pytest.mark.parametrize("code", [PlanTier.STARTER, PlanTier.GROWTH, PlanTier.ENTERPRISE])
def test_super_admin_assigns_each_plan(client, db_session, override_authenticated_user, code):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    plans = _seed_catalog(db_session)
    tenant = Tenant(name=f"Tenant {code.value}", slug=f"tenant-{code.value}")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    response = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": code.value})

    assert response.status_code == 200
    assert response.json()["plan"]["code"] == code.value
    assert response.json()["plan"]["name"] == plans[[p.code for p in plans].index(code)].name


def test_super_admin_changes_and_reassigns_plan_idempotently(client, db_session, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    plans = _seed_catalog(db_session)
    tenant = Tenant(name="Changing Tenant", slug="changing-tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    old_updated_at = tenant.updated_at

    response = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "starter"})
    assert response.status_code == 200
    db_session.expire_all()
    tenant = db_session.get(Tenant, tenant.id)
    assert tenant.plan_id == plans[0].id
    first_updated_at = tenant.updated_at

    response = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "growth"})
    assert response.status_code == 200
    assert response.json()["plan"]["code"] == "growth"
    db_session.expire_all()
    tenant = db_session.get(Tenant, tenant.id)
    assert tenant.plan_id == plans[1].id
    assert tenant.updated_at >= first_updated_at

    response = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "growth"})
    assert response.status_code == 200
    db_session.expire_all()
    tenant = db_session.get(Tenant, tenant.id)
    assert tenant.plan_id == plans[1].id
    assert tenant.updated_at >= first_updated_at + timedelta(microseconds=-1)
    assert tenant.updated_at != old_updated_at


@pytest.mark.parametrize("role", [r for r in Role if r is not Role.SUPER_ADMIN])
def test_assign_plan_rejects_non_super_admin_roles(client, db_session, override_authenticated_user, role):
    override_authenticated_user(make_authenticated_user(role))
    _seed_catalog(db_session)
    tenant = Tenant(name="Denied Tenant", slug=f"denied-plan-{role.value}")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    response = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "starter"})

    assert response.status_code == 403
    assert tenant.plan_id is None


def test_assign_plan_requires_authentication(client, db_session):
    _seed_catalog(db_session)
    tenant = Tenant(name="Anonymous Tenant", slug="anonymous-plan")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "starter"}).status_code == 401


def test_assign_plan_unknown_tenant_is_404(client, db_session, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)

    response = client.post("/tenants/999999/plan", json={"plan_code": "starter"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found"}


@pytest.mark.parametrize("payload", ["missing", {"plan_code": "invalid"}, {"plan_code": ""}, {"plan_code": "   "}, {"plan_code": 123}, {"plan_code": None}, {"plan_code": "x" * 33}])
def test_assign_plan_invalid_code_is_422(client, db_session, override_authenticated_user, payload):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)
    tenant = Tenant(name="Validation Tenant", slug="validation-plan")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    body = {} if payload == "missing" else payload

    response = client.post(f"/tenants/{tenant.id}/plan", json=body)

    assert response.status_code == 422
    assert "plan_code" in response.text


def test_assign_plan_retired_plan_is_409(client, db_session, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    plan = Plan(code=PlanTier.STARTER, name="Retired Starter", is_active=False)
    db_session.add(plan)
    tenant = Tenant(name="Retired Tenant", slug="retired-plan")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    response = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "starter"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Plan is no longer active"}
    db_session.expire_all()
    assert db_session.get(Tenant, tenant.id).plan_id is None


def test_list_plans_returns_catalog_in_seed_order_including_retired(client, db_session, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    plans = _seed_catalog(db_session)
    plans[-1].is_active = False
    plans[-1].name = "Retired Enterprise"
    db_session.commit()

    response = client.get("/tenants/plans")

    assert response.status_code == 200
    body = response.json()
    assert [p["code"] for p in body[:3]] == ["starter", "growth", "enterprise"]
    assert "Retired Enterprise" in [p["name"] for p in body]
    assert all(p["is_active"] in (True, False) for p in body)


@pytest.mark.parametrize("role", [r for r in Role if r is not Role.SUPER_ADMIN])
def test_list_plans_rejects_non_super_admin_roles(client, db_session, override_authenticated_user, role):
    override_authenticated_user(make_authenticated_user(role))
    _seed_catalog(db_session)

    response = client.get("/tenants/plans")

    assert response.status_code == 403
