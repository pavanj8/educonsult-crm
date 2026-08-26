"""Tests for the platform-level subscription Plan model (E9 task #105).

Covers:

* Column shape (the migration's contract -- if a column gets dropped
  here, the matching ``test_alembic_upgrade_head_records_revision``
  assertion in ``tests/database/test_alembic.py`` should fail too,
  but the closer-to-the-model test here catches it first).
* Round-trip of every field through SQL, including the NULL/unlimited
  semantics of the Enterprise tier (Requirements §4).
* Tier-code uniqueness so duplicate seed runs cannot silently double-
  insert the same tier.
* Tier-code round-trip through the SQLAlchemy ``Enum`` (the ``code``
  column stores the ``PlanTier.value`` string, not the enum member).
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models.plan import Plan, PlanTier


def test_plan_model_has_required_columns():
    column_names = {column.key for column in inspect(Plan).columns}
    assert column_names == {
        "id",
        "code",
        "name",
        "description",
        "max_branches",
        "max_staff",
        "max_students",
        "price_in_cents",
        "currency",
        "is_active",
        "created_at",
        "updated_at",
    }


def test_plan_persists_starter_row(db_session):
    """The Starter tier persists with concrete numeric limits (Requirements §4)."""
    now = datetime.now(timezone.utc)
    plan = Plan(
        code=PlanTier.STARTER,
        name="Starter",
        description="Single-branch consultancies, limited staff/students.",
        max_branches=1,
        max_staff=5,
        max_students=50,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert plan.id is not None
    # The enum column stores the string ``value`` so the wire format is
    # stable; the ORM round-trip is via the PlanTier member.
    assert plan.code == PlanTier.STARTER
    assert plan.code.value == "starter"
    assert plan.name == "Starter"
    assert plan.max_branches == 1
    assert plan.max_staff == 5
    assert plan.max_students == 50
    # is_active defaults to True on the column so the seed row for the
    # Starter tier shows up as sellable without an explicit override.
    assert plan.is_active is True
    assert plan.created_at is not None
    assert plan.updated_at is not None


def test_plan_enterprise_row_advertises_unlimited_limits(db_session):
    """Enterprise tiers use NULL limits to mean 'unlimited' (Requirements §4).

    Concretely: per Requirements §4 the Enterprise tier is
    'unlimited/custom'. Modeling that as NULL (rather than a magic
    sentinel like 2**31 - 1) keeps the E9 task #107 enforcement
    layer's branching trivial: ``if plan.max_branches is None:
    no_cap``. This test pins that contract.
    """
    now = datetime.now(timezone.utc)
    plan = Plan(
        code=PlanTier.ENTERPRISE,
        name="Enterprise",
        description="Unlimited branches, staff, and students.",
        max_branches=None,
        max_staff=None,
        max_students=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert plan.code == PlanTier.ENTERPRISE
    assert plan.code.value == "enterprise"
    # NULL means unlimited -- enforced as such by E9 task #107.
    assert plan.max_branches is None
    assert plan.max_staff is None
    assert plan.max_students is None


def test_plan_growth_row_has_higher_limits_than_starter(db_session):
    """The Growth tier advertises higher numeric limits than Starter (Requirements §4)."""
    now = datetime.now(timezone.utc)
    starter = Plan(
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
        created_at=now,
        updated_at=now,
    )
    growth = Plan(
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=10,
        max_staff=50,
        max_students=1000,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([starter, growth])
    db_session.commit()

    assert growth.max_branches > starter.max_branches
    assert growth.max_staff > starter.max_staff
    assert growth.max_students > starter.max_students


def test_plan_code_is_unique(db_session):
    """The ``code`` column is unique -- duplicate seed rows are rejected."""
    now = datetime.now(timezone.utc)
    first = Plan(
        code=PlanTier.STARTER,
        name="Starter A",
        created_at=now,
        updated_at=now,
    )
    second = Plan(
        code=PlanTier.STARTER,
        name="Starter B (duplicate code)",
        created_at=now,
        updated_at=now,
    )
    db_session.add(first)
    db_session.commit()
    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_plan_is_active_round_trips(db_session):
    """Retired tiers persist with ``is_active=False`` so historical data stays readable."""
    now = datetime.now(timezone.utc)
    plan = Plan(
        code=PlanTier.STARTER,
        name="Starter (retired)",
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert plan.is_active is False


def test_plan_description_is_optional(db_session):
    """``description`` is nullable -- a freshly-seeded plan may have no blurb yet."""
    now = datetime.now(timezone.utc)
    plan = Plan(
        code=PlanTier.STARTER,
        name="Starter",
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert plan.description is None


def test_plan_tier_enum_values_match_requirements():
    """The ``PlanTier`` enum exposes the three tiers from Requirements §4.

    This is the contract that E9 task #106 (assign/change plan API)
    and #107 (limit enforcement) both rely on; renaming any value is
    a breaking change.
    """
    assert {tier.value for tier in PlanTier} == {"starter", "growth", "enterprise"}


def test_plan_pricing_fields_persist(db_session):
    """Pricing fields (price_in_cents, currency) persist correctly."""
    now = datetime.now(timezone.utc)
    plan = Plan(
        code=PlanTier.STARTER,
        name="Starter",
        description="Single-branch tier",
        max_branches=1,
        max_staff=5,
        max_students=50,
        price_in_cents=499900,  # ₹4,999
        currency="INR",
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert plan.price_in_cents == 499900
    assert plan.currency == "INR"


def test_plan_price_in_cents_defaults_to_zero(db_session):
    """price_in_cents defaults to 0 when not specified."""
    now = datetime.now(timezone.utc)
    plan = Plan(
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    # Column has server_default="0" in the migration
    assert plan.price_in_cents == 0


def test_plan_currency_defaults_to_inr(db_session):
    """currency defaults to INR when not specified."""
    now = datetime.now(timezone.utc)
    plan = Plan(
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
        price_in_cents=499900,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert plan.currency == "INR"
