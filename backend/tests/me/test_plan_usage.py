"""
Tests for GET /me/plan-usage endpoint (E45; Journey J38).

Tests the owner-only plan and usage summary endpoint that returns the
tenant's assigned subscription plan and current usage counts.
"""

from __future__ import annotations

from fastapi import status
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user, make_db_user
from tests.branches.helpers import seed_branch


def _create_tenant(db_session: Session, *, name: str = "Test Tenant", slug: str = "test-tenant") -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _create_plan(
    db_session: Session,
    *,
    tier: PlanTier = PlanTier.STARTER,
    name: str = "Test Plan",
    max_branches: int | None = 1,
    max_staff: int | None = 5,
    max_students: int | None = 50,
) -> Plan:
    """Create a test plan."""
    plan = Plan(
        code=tier,
        name=name,
        max_branches=max_branches,
        max_staff=max_staff,
        max_students=max_students,
        is_active=True,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


def _auth_for(user) -> object:
    """Create authenticated user object for a user."""
    return make_authenticated_user(
        user.role,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


# ---------------------------------------------------------------------------
# Auth and role gating
# ---------------------------------------------------------------------------


def test_plan_and_usage_requires_owner_auth(
    client, db_session: Session, override_authenticated_user
):
    """Endpoint requires authentication as a consultancy owner."""
    tenant = _create_tenant(db_session)
    _ = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )

    override_authenticated_user(_auth_for(owner))

    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status.HTTP_200_OK


def test_plan_and_usage_denies_non_owner(
    client, db_session: Session, override_authenticated_user
):
    """Endpoint rejects non-owner roles (student, counselor, verifier, etc.)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    # Test student
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(student))
    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Only consultancy owners can access this endpoint" in response.json()["detail"]

    # Test counselor
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))
    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_plan_and_usage_denies_unauthenticated(client):
    """Endpoint rejects unauthenticated requests."""
    response = client.get("/me/plan-usage")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Plan and usage data
# ---------------------------------------------------------------------------


def test_plan_and_usage_returns_plan_and_usage(
    client, db_session: Session, override_authenticated_user
):
    """Endpoint returns plan details and usage counts."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    plan = _create_plan(
        db_session,
        tier=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    tenant.plan_id = plan.id
    db_session.commit()

    # Create some test data
    branch2 = Branch(name="Branch 2", city="City 2", tenant_id=tenant.id)
    db_session.add(branch2)

    # Create staff users
    staff1 = User(
        email="staff1@example.com",
        password_hash="hash",
        role=Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    staff2 = User(
        email="staff2@example.com",
        password_hash="hash",
        role=Role.BRANCH_MANAGER,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    db_session.add_all([staff1, staff2])

    # Create student users
    student1 = User(
        email="student1@example.com",
        password_hash="hash",
        role=Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    student2 = User(
        email="student2@example.com",
        password_hash="hash",
        role=Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch2.id,
    )
    student3 = User(
        email="student3@example.com",
        password_hash="hash",
        role=Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    db_session.add_all([student1, student2, student3])
    db_session.commit()

    override_authenticated_user(_auth_for(owner))

    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Check plan details
    assert data["plan"] is not None
    assert data["plan"]["code"] == "starter"
    assert data["plan"]["name"] == "Starter"
    assert data["plan"]["max_branches"] == 1
    assert data["plan"]["max_staff"] == 5
    assert data["plan"]["max_students"] == 50
    assert data["plan"]["is_active"] is True

    # Check usage counts
    assert data["usage"]["branches"] == 2
    assert data["usage"]["staff"] == 2  # Only staff, not owner
    assert data["usage"]["students"] == 3


def test_plan_and_usage_with_null_plan(
    client, db_session: Session, override_authenticated_user
):
    """Endpoint returns null plan when tenant has no plan assigned."""
    tenant = _create_tenant(db_session)
    _ = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    # Ensure tenant has no plan
    assert tenant.plan_id is None

    override_authenticated_user(_auth_for(owner))

    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["plan"] is None
    assert "usage" in data
    assert data["usage"]["branches"] >= 0
    assert data["usage"]["staff"] >= 0
    assert data["usage"]["students"] >= 0


def test_plan_and_usage_with_enterprise_unlimited(
    client, db_session: Session, override_authenticated_user
):
    """Endpoint returns null limits for enterprise (unlimited) plan."""
    tenant = _create_tenant(db_session)
    _ = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    plan = _create_plan(
        db_session,
        tier=PlanTier.ENTERPRISE,
        name="Enterprise",
        max_branches=None,
        max_staff=None,
        max_students=None,
    )
    tenant.plan_id = plan.id
    db_session.commit()

    override_authenticated_user(_auth_for(owner))

    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["plan"]["code"] == "enterprise"
    assert data["plan"]["max_branches"] is None
    assert data["plan"]["max_staff"] is None
    assert data["plan"]["max_students"] is None


def test_plan_and_usage_usage_counts_exclude_owner(
    client, db_session: Session, override_authenticated_user
):
    """Usage counts exclude the owner from staff count."""
    tenant = _create_tenant(db_session)
    _ = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    plan = _create_plan(db_session)
    tenant.plan_id = plan.id
    db_session.commit()

    override_authenticated_user(_auth_for(owner))

    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Owner is not counted, only other staff roles
    assert data["usage"]["staff"] == 0


def test_plan_and_usage_counts_deactivated_students(
    client, db_session: Session, override_authenticated_user
):
    """Usage counts include deactivated students (they still count toward limit)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    plan = _create_plan(db_session)
    tenant.plan_id = plan.id
    db_session.commit()

    # Create active and deactivated students
    active_student = User(
        email="active@example.com",
        password_hash="hash",
        role=Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        is_active=True,
    )
    deactivated_student = User(
        email="inactive@example.com",
        password_hash="hash",
        role=Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        is_active=False,
    )
    db_session.add_all([active_student, deactivated_student])
    db_session.commit()

    override_authenticated_user(_auth_for(owner))

    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Both students are counted (deactivated still occupies a seat)
    assert data["usage"]["students"] == 2


def test_plan_and_usage_cross_tenant_isolation(
    client, db_session: Session, override_authenticated_user
):
    """Endpoint only returns data for the authenticated user's tenant."""
    tenant1 = _create_tenant(db_session, name="Tenant 1", slug="tenant-1")
    _ = seed_branch(db_session, tenant_id=tenant1.id)
    owner1 = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant1.id, branch_id=None
    )
    plan1 = _create_plan(
        db_session,
        tier=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    tenant1.plan_id = plan1.id

    tenant2 = _create_tenant(db_session, name="Tenant 2", slug="tenant-2")
    _ = seed_branch(db_session, tenant_id=tenant2.id)
    _ = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant2.id, branch_id=None
    )
    plan2 = _create_plan(
        db_session,
        tier=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=20,
        max_students=100,
    )
    tenant2.plan_id = plan2.id

    # Create a branch in each tenant
    extra_branch = Branch(name="Extra Branch", city="Extra City", tenant_id=tenant2.id)
    db_session.add(extra_branch)
    db_session.commit()

    # First owner should only see their own tenant's data
    override_authenticated_user(_auth_for(owner1))

    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["plan"]["code"] == "starter"
    assert data["usage"]["branches"] == 1  # Only their own branch


def test_plan_and_usage_without_tenant_id(
    client, db_session: Session, override_authenticated_user
):
    """Endpoint returns 403 for authenticated user without tenant_id."""
    # This should never happen in practice (owner role requires tenant),
    # but we test the defensive check
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=None, branch_id=None
    )
    override_authenticated_user(_auth_for(owner))

    response = client.get(
        "/me/plan-usage",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN



