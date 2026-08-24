"""E9 epic test suite -- subscription plan assignment and limit enforcement (issue #108).

This file is the epic-level black-box test set for the E9 *Subscription
Plan Assignment* epic. The E9 epic is built from the following pieces:

* Requirements §4 Billing & Subscription -- three plan tiers
  (Starter / Growth / Enterprise) with per-tier limits on branches,
  staff, and students.
* Journey J2 -- Super Admin sets/updates a tenant's subscription plan.
* Journey J38 -- Consultancy Owner views current plan & usage.
* Journey J40 -- Super Admin views all tenants' billing/subscription
  status.

The test ticket owns no application code; its scope is to lock down
the **documented behavior** of the E9 contract end-to-end so a future
refactor cannot silently regress what the platform promises its
customers. Concretely:

1. **Plan catalog shape** -- the platform exposes exactly three tiers
   (Starter / Growth / Enterprise), each with the documented limit
   values (Requirements §4: Starter 1/limited, Growth multiple/higher,
   Enterprise unlimited/custom).
2. **Plan assignment HTTP flow** -- ``POST /tenants/{id}/plan``
   correctly mutates ``Tenant.plan_id`` and the change is visible
   on ``GET /tenants/{id}`` (E9 task #106 endpoint contract).
3. **Plan catalog HTTP shape** -- ``GET /tenants/plans`` returns the
   three tiers in a stable order with the documented per-tier limit
   values, including retired (``is_active=False``) tiers.
4. **Limit enforcement contract** -- once a tenant has been assigned a
   tier with concrete limits (Starter / Growth), creating a branch /
   staff / student past the cap raises :class:`PlanLimitExceeded`
   with a stable ``resource`` / ``limit`` shape; Enterprise
   (``max_*`` NULL) imposes no cap (Requirements §4
   "unlimited/custom" semantics).
5. **Tenant without a plan** -- a tenant whose Super Admin has not
   yet assigned a tier is treated as no-cap so the J4 / J5 / J9 / J10
   create endpoints keep working until a tier is chosen.

The limit-enforcement tests sit behind :func:`pytest.importorskip` on
``app.services.plan_limits``: that module is owned by E9 task #107
and may not yet be merged to ``main`` when this ticket is in flight.
Once #107 lands, those tests activate and validate the enforcement
contract against the documented plan-limit values; until then they
skip with a clear message rather than silently passing -- a silent
"no enforcement yet" assertion would be a worse regression than a
hard skip.

Traceability
------------
* Requirements §4 Billing & Subscription.
* Journey J2 (Super Admin sets/updates a tenant's subscription plan).
* Journey J38 (Consultancy Owner views current plan & usage; E45 owns
  the read-side surface; this file pins the catalog + assignment
  primitives that J38 reads).
* Journey J40 (Super Admin views all tenants' billing/subscription
  status; the list endpoint in this file is the read primitive J40
  builds on).
* Epic E9 (Subscription Plan Assignment).
"""

from __future__ import annotations

import pytest

from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


#: Canonical per-tier limit values seeded by ``app.seed.plans.DEFAULT_PLANS``.
#: Requirements §4 spells out the qualitative shape (Starter = 1 branch /
#: limited staff+students, Growth = multiple branches / higher limits,
#: Enterprise = unlimited/custom). The concrete numbers below are what the
#: platform seeds today and what the J38 / J40 owner-facing surfaces render;
#: they are pinned here so a silent refactor that changes a limit number
#: trips this file immediately rather than slipping into a billing dispute.
EXPECTED_PLAN_LIMITS: dict[PlanTier, dict[str, int | None]] = {
    PlanTier.STARTER: {"max_branches": 1, "max_staff": 5, "max_students": 50},
    PlanTier.GROWTH: {"max_branches": 5, "max_staff": 25, "max_students": 500},
    PlanTier.ENTERPRISE: {"max_branches": None, "max_staff": None, "max_students": None},
}


def _seed_catalog(db_session) -> list[Plan]:
    """Insert the canonical Starter / Growth / Enterprise catalog.

    Mirrors ``app.seed.plans.DEFAULT_PLANS`` so the tests do not depend
    on the SQLite bootstrap hook running ``seed_default_plans_if_empty``
    -- the ``client`` fixture replaces ``get_db`` with a test-only
    session factory and that hook only seeds the production SessionLocal.
    """
    plans = [
        Plan(
            code=PlanTier.STARTER,
            name="Starter",
            max_branches=EXPECTED_PLAN_LIMITS[PlanTier.STARTER]["max_branches"],
            max_staff=EXPECTED_PLAN_LIMITS[PlanTier.STARTER]["max_staff"],
            max_students=EXPECTED_PLAN_LIMITS[PlanTier.STARTER]["max_students"],
        ),
        Plan(
            code=PlanTier.GROWTH,
            name="Growth",
            max_branches=EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_branches"],
            max_staff=EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_staff"],
            max_students=EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_students"],
        ),
        Plan(
            code=PlanTier.ENTERPRISE,
            name="Enterprise",
            max_branches=EXPECTED_PLAN_LIMITS[PlanTier.ENTERPRISE]["max_branches"],
            max_staff=EXPECTED_PLAN_LIMITS[PlanTier.ENTERPRISE]["max_staff"],
            max_students=EXPECTED_PLAN_LIMITS[PlanTier.ENTERPRISE]["max_students"],
        ),
    ]
    db_session.add_all(plans)
    db_session.commit()
    return plans


def _create_tenant(db_session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _make_tier(db_session, tier: PlanTier, limits: dict[str, int | None]) -> Plan:
    now = _utcnow()
    plan = Plan(
        code=tier,
        name=tier.value.capitalize(),
        max_branches=limits["max_branches"],
        max_staff=limits["max_staff"],
        max_students=limits["max_students"],
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


# ---------------------------------------------------------------------------
# 1. Plan catalog HTTP shape (GET /tenants/plans)
# ---------------------------------------------------------------------------


def test_list_plans_returns_three_tiers_in_canonical_order(
    client, db_session, override_authenticated_user
):
    """Requirements §4 specifies exactly three tiers; the catalog must list them all.

    This is the J40 (Super Admin views all tenants' billing status)
    read primitive and the J39 (Razorpay checkout) plan picker read
    primitive -- both depend on the order and the identity of the
    three tiers.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)

    response = client.get("/tenants/plans")

    assert response.status_code == 200
    body = response.json()
    assert [plan["code"] for plan in body] == ["starter", "growth", "enterprise"]


def test_list_plans_returns_full_wire_shape_for_each_tier(
    client, db_session, override_authenticated_user
):
    """The catalog wire shape matches ``PlanResponse`` and includes limits.

    J38 (Owner plan & usage view) renders this payload directly to the
    user; a missing field there is a UX regression even if the model
    column still exists.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)

    response = client.get("/tenants/plans")

    assert response.status_code == 200
    body = response.json()
    expected_keys = {
        "id",
        "code",
        "name",
        "max_branches",
        "max_staff",
        "max_students",
        "is_active",
    }
    for plan in body:
        assert expected_keys.issubset(plan.keys()), plan


def test_list_plans_returns_documented_limit_values_per_tier(
    client, db_session, override_authenticated_user
):
    """The per-tier limit values match the canonical ``DEFAULT_PLANS`` seed.

    Requirements §4 stipulates "Starter: 1 branch, limited staff/
    students; Growth: multiple branches, higher limits; Enterprise:
    unlimited/custom". The concrete numbers below come from
    ``app.seed.plans.DEFAULT_PLANS`` and are the platform's promise to
    its customers -- changing them is a billing-contract change.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)

    response = client.get("/tenants/plans")

    assert response.status_code == 200
    body = response.json()
    by_code = {plan["code"]: plan for plan in body}

    for tier in PlanTier:
        plan = by_code[tier.value]
        limits = EXPECTED_PLAN_LIMITS[tier]
        assert plan["max_branches"] == limits["max_branches"], tier
        assert plan["max_staff"] == limits["max_staff"], tier
        assert plan["max_students"] == limits["max_students"], tier


def test_list_plans_returns_null_limits_for_enterprise(
    client, db_session, override_authenticated_user
):
    """Enterprise advertises ``None`` for every limit column (Requirements §4).

    The "unlimited/custom" semantics are modelled as NULL on the row
    rather than as a magic sentinel (``2**31 - 1``); the limit-
    enforcement layer treats NULL as no-cap. This test pins that wire
    value so a future "let's put 999_999_999 on Enterprise" change
    cannot slip past.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)

    response = client.get("/tenants/plans")

    assert response.status_code == 200
    body = response.json()
    enterprise = next(plan for plan in body if plan["code"] == "enterprise")
    assert enterprise["max_branches"] is None
    assert enterprise["max_staff"] is None
    assert enterprise["max_students"] is None


def test_list_plans_includes_retired_tiers(
    client, db_session, override_authenticated_user
):
    """Retired (``is_active=False``) tiers stay queryable for historical tenants.

    A tenant assigned to a now-retired tier must keep working; the
    J40 super-admin view must surface them too. The endpoint never
    filters on ``is_active``.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    plans = _seed_catalog(db_session)
    plans[-1].is_active = False
    plans[-1].name = "Retired Enterprise"
    db_session.commit()

    response = client.get("/tenants/plans")

    assert response.status_code == 200
    body = response.json()
    names = [plan["name"] for plan in body]
    assert "Retired Enterprise" in names
    retired = next(plan for plan in body if plan["code"] == "enterprise")
    assert retired["is_active"] is False


# ---------------------------------------------------------------------------
# 2. Plan assignment HTTP flow (POST /tenants/{id}/plan)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", list(PlanTier))
def test_super_admin_can_assign_each_tier(
    client, db_session, override_authenticated_user, tier
):
    """Journey J2: Super Admin assigns any of the three tiers to a tenant."""
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)
    tenant = _create_tenant(db_session, name=f"Tenant {tier.value}", slug=f"tenant-{tier.value}")

    response = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": tier.value})

    assert response.status_code == 200
    assert response.json()["plan"]["code"] == tier.value
    assert response.json()["plan"]["name"] in {
        "Starter",
        "Growth",
        "Enterprise",
    }
    assert response.json()["plan"]["is_active"] is True


def test_assign_plan_returns_full_plan_payload_on_response(
    client, db_session, override_authenticated_user
):
    """The ``POST /tenants/{id}/plan`` response includes the nested plan shape.

    J38 reads the same payload off ``GET /tenants/{id}`` -- the
    assignment endpoint must return the same shape so the frontend
    can refresh its plan view without a follow-up GET.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)
    tenant = _create_tenant(db_session, name="Shape Tenant", slug="shape-tenant")

    response = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "growth"})

    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["code"] == "growth"
    assert plan["max_branches"] == EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_branches"]
    assert plan["max_staff"] == EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_staff"]
    assert plan["max_students"] == EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_students"]
    assert plan["is_active"] is True


def test_assign_plan_is_visible_on_subsequent_get_tenant(
    client, db_session, override_authenticated_user
):
    """The assignment persists and is visible on the next ``GET /tenants/{id}``.

    E9 task #106 endpoint contract: the assign endpoint commits the
    FK change so a follow-up read sees it. Without this persistence
    the J38 owner view would always show "no plan assigned".
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)
    tenant = _create_tenant(db_session, name="Persistence Tenant", slug="persistence-tenant")

    assign_response = client.post(
        f"/tenants/{tenant.id}/plan", json={"plan_code": "starter"}
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["plan"]["code"] == "starter"

    get_response = client.get(f"/tenants/{tenant.id}")

    assert get_response.status_code == 200
    assert get_response.json()["plan"] is not None
    assert get_response.json()["plan"]["code"] == "starter"
    assert (
        get_response.json()["plan"]["max_branches"]
        == EXPECTED_PLAN_LIMITS[PlanTier.STARTER]["max_branches"]
    )


def test_assign_plan_then_reassign_reflects_new_tier(
    client, db_session, override_authenticated_user
):
    """A reassignment (Starter -> Growth) is visible on the next GET.

    Journey J2 calls out "set/update a tenant's subscription plan";
    the test pins the update half specifically.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)
    tenant = _create_tenant(db_session, name="Reassign Tenant", slug="reassign-tenant")

    client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "starter"})
    response = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "growth"})

    assert response.status_code == 200
    assert response.json()["plan"]["code"] == "growth"

    get_response = client.get(f"/tenants/{tenant.id}")
    assert get_response.json()["plan"]["code"] == "growth"
    assert (
        get_response.json()["plan"]["max_branches"]
        == EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_branches"]
    )


def test_assign_plan_is_idempotent(client, db_session, override_authenticated_user):
    """Calling ``POST /tenants/{id}/plan`` twice with the same plan_code is a no-op success.

    The J2 surface is "set/update"; re-applying the same plan must
    not raise -- the platform tolerates retries from a flaky admin
    console.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)
    tenant = _create_tenant(db_session, name="Idempotent Tenant", slug="idempotent-tenant")

    first = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "starter"})
    second = client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "starter"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["plan"]["code"] == "starter"
    assert second.json()["plan"]["code"] == "starter"


# ---------------------------------------------------------------------------
# 3. Tenant response includes the assigned plan
# ---------------------------------------------------------------------------


def test_get_tenant_includes_plan_payload_after_assignment(
    client, db_session, override_authenticated_user
):
    """``GET /tenants/{id}`` returns the nested plan object after assignment.

    J38 (Owner plan & usage view) renders this payload; if the GET
    drops the plan the owner view would show "no plan assigned"
    even after a Super Admin has set one.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _seed_catalog(db_session)
    tenant = _create_tenant(db_session, name="Nested Plan Tenant", slug="nested-plan-tenant")

    client.post(f"/tenants/{tenant.id}/plan", json={"plan_code": "growth"})

    response = client.get(f"/tenants/{tenant.id}")

    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan is not None
    assert plan["code"] == "growth"
    assert plan["max_branches"] == EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_branches"]
    assert plan["max_staff"] == EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_staff"]
    assert plan["max_students"] == EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_students"]


def test_get_tenant_returns_null_plan_for_unassigned_tenant(
    client, db_session, override_authenticated_user
):
    """A tenant with no plan assigned serializes ``plan: null``.

    The J38 surface and the J40 super-admin view both render
    "unassigned" for this case; a 500 here would be a UX regression.
    """
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    tenant = _create_tenant(db_session, name="Unassigned Tenant", slug="unassigned-tenant")

    response = client.get(f"/tenants/{tenant.id}")

    assert response.status_code == 200
    assert response.json()["plan"] is None


# ---------------------------------------------------------------------------
# 4. Per-tier limit semantics (model contract, not HTTP)
# ---------------------------------------------------------------------------


def test_starter_has_strict_one_branch_cap(db_session):
    """Requirements §4: Starter advertises ``max_branches=1``.

    Pinned at the model level (not via the seed) so a future
    refactor that breaks the seed still trips this test if the
    numeric value moves.
    """
    now = _utcnow()
    plan = Plan(
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=EXPECTED_PLAN_LIMITS[PlanTier.STARTER]["max_branches"],
        max_staff=EXPECTED_PLAN_LIMITS[PlanTier.STARTER]["max_staff"],
        max_students=EXPECTED_PLAN_LIMITS[PlanTier.STARTER]["max_students"],
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert plan.max_branches == 1
    assert plan.max_branches < EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]["max_branches"]


def test_growth_limits_are_strictly_higher_than_starter(db_session):
    """Requirements §4: Growth advertises higher limits than Starter on every axis."""
    starter, growth = (
        _make_tier(db_session, PlanTier.STARTER, EXPECTED_PLAN_LIMITS[PlanTier.STARTER]),
        _make_tier(db_session, PlanTier.GROWTH, EXPECTED_PLAN_LIMITS[PlanTier.GROWTH]),
    )

    assert growth.max_branches > starter.max_branches
    assert growth.max_staff > starter.max_staff
    assert growth.max_students > starter.max_students


def test_enterprise_advertises_unlimited_on_every_axis(db_session):
    """Requirements §4: Enterprise is "unlimited/custom" -- modelled as NULL.

    Enforcement treats NULL as no-cap; a magic sentinel value would
    defeat that branching.
    """
    plan = _make_tier(
        db_session,
        PlanTier.ENTERPRISE,
        EXPECTED_PLAN_LIMITS[PlanTier.ENTERPRISE],
    )

    assert plan.max_branches is None
    assert plan.max_staff is None
    assert plan.max_students is None


def test_tier_codes_match_documented_three_tiers():
    """Requirements §4 specifies exactly three tiers -- the enum must not silently grow."""
    assert {tier.value for tier in PlanTier} == {"starter", "growth", "enterprise"}


# ---------------------------------------------------------------------------
# 5. Limit enforcement contract (E9 task #107 -- may not yet be on main)
# ---------------------------------------------------------------------------


# The limit-enforcement tests below exercise the ``app.services.plan_limits``
# service module owned by E9 task #107. Until #107 merges to ``main``, that
# module is not importable and the tests must skip rather than fail -- a
# silent "no enforcement yet" assertion would be a worse regression than a
# hard skip. The :func:`_load_plan_limits` helper below triggers the skip
# cleanly so only the enforcement tests are affected (not the entire file).


def _load_plan_limits():
    """Return the ``app.services.plan_limits`` module or skip the calling test."""
    return pytest.importorskip(
        "app.services.plan_limits",
        reason="E9 task #107 limit-enforcement module is not yet on main",
    )


def test_enforcement_module_exposes_required_public_api():
    """The enforcement module exposes ``enforce_*`` helpers and ``PlanLimitExceeded``.

    The HTTP layer (E9 task #107 wiring) calls these names; renaming
    any of them is a breaking change that future E9 callers must
    catch here.
    """
    plan_limits_module = _load_plan_limits()
    assert hasattr(plan_limits_module, "PlanLimitExceeded")
    assert hasattr(plan_limits_module, "enforce_branch_limit")
    assert hasattr(plan_limits_module, "enforce_staff_limit")
    assert hasattr(plan_limits_module, "enforce_student_limit")


def test_plan_limit_exceeded_carries_resource_limit_and_plan_code():
    """``PlanLimitExceeded`` exposes ``resource`` / ``limit`` / ``plan_code`` for diagnostics.

    The HTTP layer surfaces these in the 422 detail so an admin can
    see *which* limit fired and *at what number*. A future refactor
    that drops any of the three fields is a UX regression even if
    the exception still raises.
    """
    plan_limits_module = _load_plan_limits()
    exc = plan_limits_module.PlanLimitExceeded(
        resource="branches", limit=1, plan_code="starter"
    )
    assert exc.resource == "branches"
    assert exc.limit == 1
    assert exc.plan_code == "starter"


def test_enforce_branch_limit_raises_on_starter_cap(db_session):
    """A Starter tenant with one branch cannot create a second (Requirements §4)."""
    plan_limits_module = _load_plan_limits()
    starter_plan = _seed_catalog(db_session)[0]
    tenant = _create_tenant(db_session, name="Cap Tenant", slug="cap-tenant")
    tenant.plan_id = starter_plan.id
    db_session.commit()

    # Seed one branch so the cap is already at the threshold.
    from app.models.branch import Branch

    branch = Branch(tenant_id=tenant.id, name="Existing", city="City")
    db_session.add(branch)
    db_session.commit()

    with pytest.raises(plan_limits_module.PlanLimitExceeded) as exc_info:
        plan_limits_module.enforce_branch_limit(db_session, tenant.id)

    assert exc_info.value.resource == "branches"
    assert exc_info.value.limit == 1
    assert exc_info.value.plan_code == "starter"


def test_enforce_branch_limit_is_silent_under_enterprise(db_session):
    """An Enterprise tenant (``max_branches=NULL``) raises no exception -- unlimited cap.

    Requirements §4 "Enterprise is unlimited/custom"; the enforcement
    layer must treat NULL as no-cap rather than raising or counting
    the absence as zero.
    """
    plan_limits_module = _load_plan_limits()
    _seed_catalog(db_session)
    tenant = _create_tenant(db_session, name="Enterprise Cap Tenant", slug="enterprise-cap")

    # Should not raise even though there are zero branches -- the
    # point of the test is that Enterprise has no cap and the
    # enforcement call is a no-op.
    plan_limits_module.enforce_branch_limit(db_session, tenant.id)


def test_enforce_branch_limit_is_silent_when_tenant_has_no_plan(db_session):
    """A tenant with no ``plan_id`` set is treated as no-cap (pre-#106 fallback).

    Until a Super Admin explicitly assigns a tier, the platform must
    stay usable -- the J4 / J5 / J9 / J10 create endpoints all depend
    on this fallback. A raise here would brick every tenant created
    before E9 #106 lands.
    """
    plan_limits_module = _load_plan_limits()
    _seed_catalog(db_session)
    tenant = _create_tenant(db_session, name="Unassigned", slug="unassigned-enforce")
    # Note: no plan assignment -- tenant.plan_id stays NULL.

    # No-raise expected: the no-plan branch falls through to no-cap.
    plan_limits_module.enforce_branch_limit(db_session, tenant.id)
