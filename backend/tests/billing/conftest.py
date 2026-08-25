"""Tests for billing & subscription functionality (E46; Journey J39)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.models.user import User, Role
from app.rbac.user import AuthenticatedUser
from tests.factories.users import make_db_user


@pytest.fixture()
def razorpay_test_credentials(monkeypatch):
    """Set test Razorpay credentials for tests that need them.

    Most billing tests need valid credentials to avoid RuntimeError.
    Tests that specifically test the error case should not use this fixture.
    """
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_1234567890abcdef")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_secret_1234567890abcdef")


@pytest.fixture()
def test_plan(db_session: Session) -> Plan:
    """Create a Growth plan for testing."""
    plan = Plan(
        code=PlanTier.GROWTH,
        name="Growth",
        description="Growth tier for growing consultancies",
        max_branches=5,
        max_staff=25,
        max_students=500,
        price_in_cents=100000,  # 1000.00 INR in paisa
        currency="INR",
        is_active=True,
    )
    db_session.add(plan)
    db_session.commit()
    return plan


@pytest.fixture()
def enterprise_plan(db_session: Session) -> Plan:
    """Create an Enterprise plan for testing."""
    plan = Plan(
        code=PlanTier.ENTERPRISE,
        name="Enterprise",
        description="Enterprise tier with unlimited resources",
        max_branches=None,  # unlimited
        max_staff=None,  # unlimited
        max_students=None,  # unlimited
        price_in_cents=500000,  # 5000.00 INR in paisa
        currency="INR",
        is_active=True,
    )
    db_session.add(plan)
    db_session.commit()
    return plan


@pytest.fixture()
def inactive_plan(db_session: Session) -> Plan:
    """Create an inactive Starter plan for testing."""
    plan = Plan(
        code=PlanTier.STARTER,
        name="Starter",
        description="Starter tier (retired)",
        max_branches=1,
        max_staff=5,
        max_students=100,
        price_in_cents=50000,  # 500.00 INR in paisa
        currency="INR",
        is_active=False,  # Inactive
    )
    db_session.add(plan)
    db_session.commit()
    return plan


@pytest.fixture()
def owner_tenant(db_session: Session) -> Tenant:
    """Create a tenant for the owner user."""
    tenant = Tenant(
        name="Test Consultancy",
        slug="test-consultancy",
        currency="INR",
    )
    db_session.add(tenant)
    db_session.commit()
    return tenant


@pytest.fixture()
def owner_user(db_session: Session, owner_tenant: Tenant) -> User:
    """Create a consultancy owner user for testing."""
    return make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@test.com",
        tenant_id=owner_tenant.id,
        branch_id=None,
    )


@pytest.fixture()
def auth_client(client: TestClient, owner_user: User) -> TestClient:
    """Return a TestClient authenticated as the owner user."""
    from app.auth.jwt import create_access_token as _create_access_token

    token = _create_access_token(
        AuthenticatedUser(
            id=owner_user.id,
            role=owner_user.role,
            tenant_id=owner_user.tenant_id,
            branch_id=owner_user.branch_id,
        )
    )
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture()
def student_user(db_session: Session, owner_tenant: Tenant) -> User:
    """Create a student user for permission testing."""
    return make_db_user(
        db_session,
        Role.STUDENT,
        email="student@test.com",
        tenant_id=owner_tenant.id,
        branch_id=None,
    )


@pytest.fixture()
def super_admin_user(db_session: Session) -> User:
    """Create a super admin user for testing (no tenant_id)."""
    return make_db_user(
        db_session,
        Role.SUPER_ADMIN,
        email="superadmin@test.com",
        tenant_id=None,
        branch_id=None,
    )
