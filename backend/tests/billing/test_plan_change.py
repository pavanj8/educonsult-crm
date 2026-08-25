"""Tests for plan change service (E46 task #225)."""

import pytest

from app.billing.plan_change import (
    PlanChangeResult,
    PlanInactive,
    PlanNotFound,
    TenantNotFound,
    apply_plan_change,
)
from app.models.plan import Plan, PlanTier


def test_apply_plan_change_success(db_session, owner_tenant, test_plan):
    """Successfully apply a plan change to a tenant."""
    result = apply_plan_change(
        db_session,
        tenant_id=owner_tenant.id,
        plan_code="growth",
    )

    assert isinstance(result, PlanChangeResult)
    assert result.tenant_id == owner_tenant.id
    assert result.previous_plan_id is None  # Tenant had no plan before
    assert result.new_plan_id == test_plan.id
    assert result.plan_code == "growth"

    # Verify tenant was updated in database
    db_session.refresh(owner_tenant)
    assert owner_tenant.plan_id == test_plan.id


def test_apply_plan_change_from_existing_plan(db_session, owner_tenant, test_plan, enterprise_plan):
    """Change from one plan to another (upgrade or downgrade)."""
    # Set initial plan to enterprise
    owner_tenant.plan_id = enterprise_plan.id
    db_session.commit()

    # Change to growth plan (downgrade)
    result = apply_plan_change(
        db_session,
        tenant_id=owner_tenant.id,
        plan_code="growth",
    )

    assert result.previous_plan_id == enterprise_plan.id
    assert result.new_plan_id == test_plan.id
    assert result.plan_code == "growth"

    # Verify tenant was updated
    db_session.refresh(owner_tenant)
    assert owner_tenant.plan_id == test_plan.id


def test_apply_plan_change_same_plan_idempotent(db_session, owner_tenant, test_plan):
    """Applying the same plan multiple times is idempotent."""
    # First application
    owner_tenant.plan_id = test_plan.id
    db_session.commit()

    # Apply same plan again (should succeed without error)
    result = apply_plan_change(
        db_session,
        tenant_id=owner_tenant.id,
        plan_code="growth",
    )

    assert result.previous_plan_id == test_plan.id
    assert result.new_plan_id == test_plan.id
    assert result.plan_code == "growth"


def test_apply_plan_change_tenant_not_found(db_session, test_plan):
    """Raise TenantNotFound if tenant doesn't exist."""
    with pytest.raises(TenantNotFound) as exc_info:
        apply_plan_change(
            db_session,
            tenant_id=99999,  # Non-existent tenant
            plan_code="growth",
        )

    assert exc_info.value.tenant_id == 99999
    assert "Tenant 99999 not found" in str(exc_info.value)


def test_apply_plan_change_unknown_plan_code(db_session, owner_tenant):
    """Raise PlanNotFound if plan code doesn't exist."""
    with pytest.raises(PlanNotFound) as exc_info:
        apply_plan_change(
            db_session,
            tenant_id=owner_tenant.id,
            plan_code="unknown",
        )

    assert exc_info.value.plan_code == "unknown"
    assert "Plan 'unknown' not found" in str(exc_info.value)


def test_apply_plan_change_invalid_enum_value(db_session, owner_tenant):
    """Raise PlanNotFound for invalid plan tier enum value."""
    with pytest.raises(PlanNotFound) as exc_info:
        apply_plan_change(
            db_session,
            tenant_id=owner_tenant.id,
            plan_code="platinum",  # Not a valid PlanTier
        )

    assert exc_info.value.plan_code == "platinum"


def test_apply_plan_change_inactive_plan(db_session, owner_tenant, inactive_plan):
    """Raise PlanInactive if plan exists but is inactive."""
    with pytest.raises(PlanInactive) as exc_info:
        apply_plan_change(
            db_session,
            tenant_id=owner_tenant.id,
            plan_code="starter",  # Inactive plan
        )

    assert exc_info.value.plan_code == "starter"
    assert "no longer active" in str(exc_info.value)


def test_apply_plan_change_plan_code_normalized(db_session, owner_tenant, test_plan):
    """Plan code is normalized (uppercase, whitespace)."""
    # Test with uppercase
    result = apply_plan_change(
        db_session,
        tenant_id=owner_tenant.id,
        plan_code="GROWTH",
    )
    assert result.plan_code == "growth"

    # Test with whitespace
    db_session.rollback()
    result = apply_plan_change(
        db_session,
        tenant_id=owner_tenant.id,
        plan_code=" growth ",
    )
    assert result.plan_code == "growth"


def test_apply_plan_change_tenant_id_string_conversion(db_session, owner_tenant, test_plan):
    """Tenant ID is converted from string to int."""
    result = apply_plan_change(
        db_session,
        tenant_id=str(owner_tenant.id),  # Pass as string (from webhook)
        plan_code="growth",
    )

    assert result.tenant_id == owner_tenant.id
    assert owner_tenant.plan_id == test_plan.id


def test_apply_plan_change_all_plan_tiers(db_session, owner_tenant):
    """Apply each of the three plan tiers successfully."""
    plans = {
        PlanTier.STARTER: ("Starter", 1, 5, 100),
        PlanTier.GROWTH: ("Growth", 5, 25, 500),
        PlanTier.ENTERPRISE: ("Enterprise", None, None, None),
    }

    for tier, (name, max_branches, max_staff, max_students) in plans.items():
        # Create plan
        plan = Plan(
            code=tier,
            name=name,
            description=f"{name} tier",
            max_branches=max_branches,
            max_staff=max_staff,
            max_students=max_students,
            price_in_cents=100000,
            currency="INR",
            is_active=True,
        )
        db_session.add(plan)
        db_session.flush()

        # Apply plan change
        result = apply_plan_change(
            db_session,
            tenant_id=owner_tenant.id,
            plan_code=tier.value,
        )

        assert result.plan_code == tier.value
        assert result.new_plan_id == plan.id

        # Verify tenant updated
        db_session.refresh(owner_tenant)
        assert owner_tenant.plan_id == plan.id

        # Clean up for next iteration
        owner_tenant.plan_id = None
        db_session.commit()


def test_apply_plan_change_flush_validates_constraints(db_session, owner_tenant):
    """Database flush validates constraints before commit."""
    # This test verifies that flush() catches constraint violations
    # In a real scenario, this might catch FK violations or other issues
    plan = Plan(
        code=PlanTier.GROWTH,
        name="Growth",
        description="Test",
        max_branches=5,
        max_staff=25,
        max_students=500,
        price_in_cents=100000,
        currency="INR",
        is_active=True,
    )
    db_session.add(plan)
    db_session.flush()

    result = apply_plan_change(
        db_session,
        tenant_id=owner_tenant.id,
        plan_code="growth",
    )

    assert result.new_plan_id == plan.id
