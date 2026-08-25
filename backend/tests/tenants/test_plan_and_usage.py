"""Tests for the owner plan & usage view endpoint (E45; Journey J38).

Covers ``GET /tenants/me/plan-usage`` which returns the current
owner's tenant subscription plan and usage counts.

* Returns 401 when the caller is not authenticated.
* Returns 403 when the caller lacks ``billing:read_own`` permission
  (i.e., is not a consultancy owner).
* Returns the tenant's assigned plan details (or ``None`` if no plan
  has been assigned).
* Returns current usage counts for branches, staff, and students.
* Correctly reflects plan caps (including ``None`` for unlimited).
* Correctly counts only the caller's tenant's resources (no leakage
  between tenants).
"""


from app.auth import create_access_token
from app.models.branch import Branch
from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac.roles import Role
from tests.conftest import make_auth_headers
from tests.factories.ids import next_test_id
from tests.factories.users import make_authenticated_user, make_db_user


def _make_plan(db_session, *, code: PlanTier, name: str, max_branches: int | None,
               max_staff: int | None, max_students: int | None) -> Plan:
    """Create a plan row for testing."""
    from datetime import datetime, timezone

    plan = Plan(
        code=code,
        name=name,
        max_branches=max_branches,
        max_staff=max_staff,
        max_students=max_students,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


def _make_tenant(db_session, *, plan_id: int | None = None) -> Tenant:
    """Create a tenant row for testing."""
    from datetime import datetime, timezone

    seq = next_test_id()
    tenant = Tenant(
        name=f"Tenant {seq}",
        slug=f"tenant-{seq}",
        plan_id=plan_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _make_user(db_session, *, tenant_id: int, role: Role) -> User:
    """Create a user row for testing."""
    return make_db_user(db_session, role, tenant_id=tenant_id)


def _make_branch(db_session, *, tenant_id: int, name: str = "Main", city: str = "City") -> Branch:
    """Create a branch row for testing."""
    branch = Branch(
        tenant_id=tenant_id,
        name=name,
        city=city,
    )
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch


def test_plan_and_usage_returns_401_when_not_authenticated(client):
    """Unauthenticated requests are rejected."""
    response = client.get("/tenants/me/plan-usage")
    assert response.status_code == 401


def test_plan_and_usage_returns_403_for_non_owner_roles(client, db_session):
    """Only consultancy owners can view their plan and usage."""
    tenant = _make_tenant(db_session)
    
    for role in (Role.STUDENT, Role.COUNSELOR, Role.BRANCH_MANAGER, Role.RECEPTIONIST):
        user = _make_user(db_session, tenant_id=tenant.id, role=role)
        token = create_access_token(make_authenticated_user(role, user_id=user.id, tenant_id=tenant.id))
        response = client.get(
            "/tenants/me/plan-usage",
            headers=make_auth_headers(token),
        )
        assert response.status_code == 403


def test_plan_and_usage_returns_plan_details_for_owner(client, db_session):
    """An owner receives their tenant's plan details."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    owner = _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)
    token = create_access_token(make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=tenant.id))

    response = client.get(
        "/tenants/me/plan-usage",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert "plan" in data
    assert "usage" in data
    assert data["plan"]["code"] == "starter"
    assert data["plan"]["name"] == "Starter"
    assert data["plan"]["max_branches"] == 1
    assert data["plan"]["max_staff"] == 5
    assert data["plan"]["max_students"] == 50


def test_plan_and_usage_returns_null_when_no_plan_assigned(client, db_session):
    """A tenant without an assigned plan receives plan=null."""
    tenant = _make_tenant(db_session, plan_id=None)
    owner = _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)
    token = create_access_token(make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=tenant.id))

    response = client.get(
        "/tenants/me/plan-usage",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["plan"] is None
    # Usage should still be populated
    assert "usage" in data
    assert data["usage"]["branches_used"] == 0
    assert data["usage"]["staff_used"] == 0
    assert data["usage"]["students_used"] == 0
    assert data["usage"]["branches_limit"] is None
    assert data["usage"]["staff_limit"] is None
    assert data["usage"]["students_limit"] is None


def test_plan_and_usage_counts_branches(client, db_session):
    """The endpoint counts the tenant's branches correctly."""
    plan = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=20,
        max_students=200,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    owner = _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)
    token = create_access_token(make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=tenant.id))

    # Create 3 branches
    for i in range(3):
        _make_branch(db_session, tenant_id=tenant.id, name=f"Branch {i}", city=f"City {i}")

    response = client.get(
        "/tenants/me/plan-usage",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["branches_used"] == 3
    assert data["usage"]["branches_limit"] == 5


def test_plan_and_usage_counts_staff(client, db_session):
    """The endpoint counts staff accounts (all non-student roles)."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    owner = _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)
    token = create_access_token(make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=tenant.id))

    # Create various staff roles
    for role in (Role.BRANCH_MANAGER, Role.COUNSELOR, Role.DOCUMENT_VERIFIER,
                 Role.VISA_PROCESSOR, Role.RECEPTIONIST):
        _make_user(db_session, tenant_id=tenant.id, role=role)

    response = client.get(
        "/tenants/me/plan-usage",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["staff_used"] == 5
    assert data["usage"]["staff_limit"] == 5


def test_plan_and_usage_does_not_count_students_as_staff(client, db_session):
    """Students are counted in students_used, not staff_used."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=2,
        max_students=10,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    owner = _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)
    token = create_access_token(make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=tenant.id))

    # Create 1 staff and 3 students
    _make_user(db_session, tenant_id=tenant.id, role=Role.COUNSELOR)
    for _ in range(3):
        _make_user(db_session, tenant_id=tenant.id, role=Role.STUDENT)

    response = client.get(
        "/tenants/me/plan-usage",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["staff_used"] == 1
    assert data["usage"]["students_used"] == 3


def test_plan_and_usage_counts_students(client, db_session):
    """The endpoint counts student accounts correctly."""
    plan = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=20,
        max_students=200,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    owner = _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)
    token = create_access_token(make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=tenant.id))

    # Create 15 students
    for _ in range(15):
        _make_user(db_session, tenant_id=tenant.id, role=Role.STUDENT)

    response = client.get(
        "/tenants/me/plan-usage",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["students_used"] == 15
    assert data["usage"]["students_limit"] == 200


def test_plan_and_usage_returns_null_limits_for_unlimited_plan(client, db_session):
    """Enterprise plans with NULL caps return null limits in the response."""
    plan = _make_plan(
        db_session,
        code=PlanTier.ENTERPRISE,
        name="Enterprise",
        max_branches=None,
        max_staff=None,
        max_students=None,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    owner = _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)
    token = create_access_token(make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=tenant.id))

    # Create some resources
    _make_branch(db_session, tenant_id=tenant.id)
    _make_user(db_session, tenant_id=tenant.id, role=Role.COUNSELOR)
    _make_user(db_session, tenant_id=tenant.id, role=Role.STUDENT)

    response = client.get(
        "/tenants/me/plan-usage",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["branches_used"] == 1
    assert data["usage"]["branches_limit"] is None
    assert data["usage"]["staff_used"] == 1
    assert data["usage"]["staff_limit"] is None
    assert data["usage"]["students_used"] == 1
    assert data["usage"]["students_limit"] is None


def test_plan_and_usage_does_not_leak_cross_tenant_data(client, db_session):
    """The endpoint only counts resources for the caller's tenant."""
    # Create two tenants with different plans
    plan1 = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    tenant1 = _make_tenant(db_session, plan_id=plan1.id)
    owner1 = _make_user(db_session, tenant_id=tenant1.id, role=Role.CONSULTANCY_OWNER)

    plan2 = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=20,
        max_students=200,
    )
    tenant2 = _make_tenant(db_session, plan_id=plan2.id)
    owner2 = _make_user(db_session, tenant_id=tenant2.id, role=Role.CONSULTANCY_OWNER)

    # Add resources to tenant1
    _make_branch(db_session, tenant_id=tenant1.id)
    _make_user(db_session, tenant_id=tenant1.id, role=Role.COUNSELOR)
    _make_user(db_session, tenant_id=tenant1.id, role=Role.STUDENT)

    # Add resources to tenant2
    for _ in range(3):
        _make_branch(db_session, tenant_id=tenant2.id)
    for _ in range(10):
        _make_user(db_session, tenant_id=tenant2.id, role=Role.COUNSELOR)
    for _ in range(50):
        _make_user(db_session, tenant_id=tenant2.id, role=Role.STUDENT)

    # Owner 1 sees only their own tenant's counts
    token1 = create_access_token(make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner1.id, tenant_id=tenant1.id))
    response1 = client.get(
        "/tenants/me/plan-usage",
        headers=make_auth_headers(token1),
    )

    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["usage"]["branches_used"] == 1
    assert data1["usage"]["branches_limit"] == 1
    assert data1["usage"]["staff_used"] == 1
    assert data1["usage"]["staff_limit"] == 5
    assert data1["usage"]["students_used"] == 1
    assert data1["usage"]["students_limit"] == 50

    # Owner 2 sees only their own tenant's counts
    token2 = create_access_token(make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner2.id, tenant_id=tenant2.id))
    response2 = client.get(
        "/tenants/me/plan-usage",
        headers=make_auth_headers(token2),
    )

    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["usage"]["branches_used"] == 3
    assert data2["usage"]["branches_limit"] == 5
    assert data2["usage"]["staff_used"] == 10
    assert data2["usage"]["staff_limit"] == 20
    assert data2["usage"]["students_used"] == 50
    assert data2["usage"]["students_limit"] == 200
