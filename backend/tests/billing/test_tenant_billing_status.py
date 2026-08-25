"""Tests for the super admin billing status overview endpoint (E47; Journey J40).

Covers ``GET /billing/tenant-status`` which returns all tenants' billing
and subscription status with plan details and usage counts.

* Returns 401 when the caller is not authenticated.
* Returns 403 when the caller lacks ``billing:platform`` permission
  (i.e., is not a super admin).
* Returns a list of all tenants with their plan details.
* Returns correct usage counts for each tenant (branches, staff, students).
* Returns tenants without assigned plans with ``plan=null``.
* Does not leak cross-tenant data (each tenant's counts are isolated).
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


def test_tenant_billing_status_returns_401_when_not_authenticated(client):
    """Unauthenticated requests are rejected."""
    response = client.get("/billing/tenant-status")
    assert response.status_code == 401


def test_tenant_billing_status_returns_403_for_non_super_admin(client, db_session):
    """Only super admins can view all tenants' billing status."""
    tenant = _make_tenant(db_session)
    
    for role in (Role.STUDENT, Role.COUNSELOR, Role.BRANCH_MANAGER,
                 Role.RECEPTIONIST, Role.CONSULTANCY_OWNER):
        user = _make_user(db_session, tenant_id=tenant.id, role=role)
        token = create_access_token(make_authenticated_user(role, user_id=user.id, tenant_id=tenant.id))
        response = client.get(
            "/billing/tenant-status",
            headers=make_auth_headers(token),
        )
        assert response.status_code == 403


def test_tenant_billing_status_returns_empty_list_when_no_tenants(client, db_session):
    """Super admin receives an empty list when no tenants exist."""
    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_tenant_billing_status_lists_all_tenants(client, db_session):
    """Super admin receives a list of all tenants with billing status."""
    plan1 = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=6,
        max_students=50,
    )
    tenant1 = _make_tenant(db_session, plan_id=plan1.id)
    
    plan2 = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=21,
        max_students=200,
    )
    tenant2 = _make_tenant(db_session, plan_id=plan2.id)

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Verify both tenants are present
    tenant_ids = [t["tenant_id"] for t in data]
    assert tenant1.id in tenant_ids
    assert tenant2.id in tenant_ids


def test_tenant_billing_status_includes_plan_details(client, db_session):
    """Each tenant's billing status includes assigned plan details."""
    plan = _make_plan(
        db_session,
        code=PlanTier.ENTERPRISE,
        name="Enterprise",
        max_branches=None,
        max_staff=None,
        max_students=None,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    tenant_status = data[0]
    assert tenant_status["tenant_id"] == tenant.id
    assert tenant_status["tenant_name"] == tenant.name
    assert tenant_status["tenant_slug"] == tenant.slug
    assert tenant_status["plan"]["code"] == "enterprise"
    assert tenant_status["plan"]["name"] == "Enterprise"
    assert tenant_status["plan"]["max_branches"] is None
    assert tenant_status["plan"]["max_staff"] is None
    assert tenant_status["plan"]["max_students"] is None


def test_tenant_billing_status_returns_null_for_tenant_without_plan(client, db_session):
    """Tenants without an assigned plan have plan=null in the response."""
    tenant = _make_tenant(db_session, plan_id=None)

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    tenant_status = data[0]
    assert tenant_status["tenant_id"] == tenant.id
    assert tenant_status["plan"] is None
    # Usage counts should still be present
    assert "branches_used" in tenant_status
    assert "staff_used" in tenant_status
    assert "students_used" in tenant_status


def test_tenant_billing_status_counts_branches(client, db_session):
    """The endpoint counts each tenant's branches correctly."""
    plan = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=21,
        max_students=200,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    # Create an owner for the tenant
    _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)

    # Create 3 branches
    for i in range(3):
        _make_branch(db_session, tenant_id=tenant.id, name=f"Branch {i}", city=f"City {i}")

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    tenant_status = data[0]
    assert tenant_status["branches_used"] == 3


def test_tenant_billing_status_counts_staff(client, db_session):
    """The endpoint counts staff accounts (all non-student roles)."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=6,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)

    # Create owner
    _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)

    # Create various staff roles
    for role in (Role.BRANCH_MANAGER, Role.COUNSELOR, Role.DOCUMENT_VERIFIER,
                 Role.VISA_PROCESSOR, Role.RECEPTIONIST):
        _make_user(db_session, tenant_id=tenant.id, role=role)

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    tenant_status = data[0]
    # Staff count includes owner + 5 created staff = 6 total
    assert tenant_status["staff_used"] == 6


def test_tenant_billing_status_does_not_count_students_as_staff(client, db_session):
    """Students are counted in students_used, not staff_used."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=3,
        max_students=10,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)

    # Create owner
    _make_user(db_session, tenant_id=tenant.id, role=Role.CONSULTANCY_OWNER)

    # Create 1 staff and 3 students
    _make_user(db_session, tenant_id=tenant.id, role=Role.COUNSELOR)
    for _ in range(3):
        _make_user(db_session, tenant_id=tenant.id, role=Role.STUDENT)

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    tenant_status = data[0]
    # Staff count includes owner + 1 counselor = 2 total
    assert tenant_status["staff_used"] == 2
    assert tenant_status["students_used"] == 3


def test_tenant_billing_status_counts_students(client, db_session):
    """The endpoint counts student accounts correctly."""
    plan = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=21,
        max_students=200,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)

    # Create 15 students
    for _ in range(15):
        _make_user(db_session, tenant_id=tenant.id, role=Role.STUDENT)

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    tenant_status = data[0]
    assert tenant_status["students_used"] == 15


def test_tenant_billing_status_does_not_leak_cross_tenant_data(client, db_session):
    """Each tenant's usage counts are isolated; no cross-tenant leakage."""
    # Create two tenants with different plans
    plan1 = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=6,
        max_students=50,
    )
    tenant1 = _make_tenant(db_session, plan_id=plan1.id)

    plan2 = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=21,
        max_students=200,
    )
    tenant2 = _make_tenant(db_session, plan_id=plan2.id)

    # Create owners for both tenants
    _make_user(db_session, tenant_id=tenant1.id, role=Role.CONSULTANCY_OWNER)
    _make_user(db_session, tenant_id=tenant2.id, role=Role.CONSULTANCY_OWNER)

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

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Find each tenant in the response
    tenant1_status = next(t for t in data if t["tenant_id"] == tenant1.id)
    tenant2_status = next(t for t in data if t["tenant_id"] == tenant2.id)
    
    # Verify tenant1's counts are isolated
    assert tenant1_status["branches_used"] == 1
    assert tenant1_status["staff_used"] == 2  # owner + 1 counselor
    assert tenant1_status["students_used"] == 1
    
    # Verify tenant2's counts are isolated
    assert tenant2_status["branches_used"] == 3
    assert tenant2_status["staff_used"] == 11  # owner + 10 counselors
    assert tenant2_status["students_used"] == 50


def test_tenant_billing_status_includes_timestamps(client, db_session):
    """The response includes created_at and updated_at timestamps."""
    _make_tenant(db_session)

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    tenant_status = data[0]
    assert "created_at" in tenant_status
    assert "updated_at" in tenant_status
    assert tenant_status["created_at"] is not None
    assert tenant_status["updated_at"] is not None


def test_tenant_billing_status_handles_mixed_tenants_with_and_without_plans(client, db_session):
    """The endpoint correctly handles a mix of tenants with and without plans."""
    # Tenant with a plan
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=6,
        max_students=50,
    )
    tenant_with_plan = _make_tenant(db_session, plan_id=plan.id)
    _make_user(db_session, tenant_id=tenant_with_plan.id, role=Role.CONSULTANCY_OWNER)
    
    # Tenant without a plan
    tenant_without_plan = _make_tenant(db_session, plan_id=None)
    _make_user(db_session, tenant_id=tenant_without_plan.id, role=Role.CONSULTANCY_OWNER)

    super_admin = _make_user(db_session, tenant_id=None, role=Role.SUPER_ADMIN)
    token = create_access_token(make_authenticated_user(Role.SUPER_ADMIN, user_id=super_admin.id, tenant_id=None))

    response = client.get(
        "/billing/tenant-status",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Find each tenant in the response
    with_plan_status = next(t for t in data if t["tenant_id"] == tenant_with_plan.id)
    without_plan_status = next(t for t in data if t["tenant_id"] == tenant_without_plan.id)
    
    # Verify tenant with plan has plan details
    assert with_plan_status["plan"] is not None
    assert with_plan_status["plan"]["code"] == "starter"
    
    # Verify tenant without plan has null plan
    assert without_plan_status["plan"] is None
    
    # Both should have usage counts
    assert with_plan_status["staff_used"] == 1  # owner only
    assert without_plan_status["staff_used"] == 1  # owner only
