"""Seed the platform-level subscription plan catalog (E9; Journey J2).

The three tiers from Requirements §4 (Starter / Growth / Enterprise)
are a platform constant -- the same catalog is used by every tenant
choice in J2, the future Razorpay checkout in J39, the owner
plan-usage view in J38, and the super-admin billing-status view in
J40. This module is the single source of truth for the row shape
and the per-tier defaults (the limits are the ones called out in
Requirements §4 plus the conservative concrete numbers called out
in the E9 epic's task list).

The seed is *idempotent*: re-running it on a populated DB does not
duplicate rows (it skips any tier whose code already exists). It
is called from:

* the SQLite bootstrap path in :func:`app.main._ensure_sqlite_schema`
  (so the Test Agent's black-box harness always sees a populated
  catalog on first boot);
* the Alembic migration ``o8p9q0r1s2t3_create_plans_table`` if
  it ever wants to seed alongside ``op.create_table`` (it
  currently does not -- the seeder is the canonical place so
  re-running the migration on a fresh DB does not also need to
  load fixtures).

Why this lives in its own module instead of in
``app.seed.runner``:

* The plans catalog is a platform-level concern, not a per-tenant
  demo-data concern. The runner is gated on
  ``session.query(Tenant.id).first() is None`` (it only loads demo
  data on a fully empty database) and would never run on a
  real-world production DB that already has a few tenants. The plan
  catalog, by contrast, must exist before the very first tenant is
  created -- otherwise ``POST /tenants/{id}/plan`` cannot resolve a
  ``plan_code`` against any row. So the seeder runs on every boot
  of the SQLite path and is safe to call repeatedly.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.plan import Plan, PlanTier

#: Per-tier defaults spelled out in Requirements §4 Billing &
#: Subscription. ``None`` for the limit columns means "unlimited"
#: (Requirements §4 explicitly says Enterprise is "unlimited/custom";
#: we model that with NULL on the column rather than a magic
#: ``2**31 - 1`` sentinel, see :mod:`app.models.plan`).
#: Prices are in paisa (smallest currency unit for INR) for Razorpay
#: checkout (E46; Journey J39).
DEFAULT_PLANS: tuple[dict, ...] = (
    {
        "code": PlanTier.STARTER,
        "name": "Starter",
        "description": (
            "Single branch with limited staff/student headcount. "
            "Suited to early-stage consultancies."
        ),
        "max_branches": 1,
        "max_staff": 5,
        "max_students": 50,
        "price_in_cents": 499900,  # ₹4,999
        "currency": "INR",
    },
    {
        "code": PlanTier.GROWTH,
        "name": "Growth",
        "description": (
            "Multiple branches with higher staff/student caps. "
            "The mid-market tier."
        ),
        "max_branches": 5,
        "max_staff": 25,
        "max_students": 500,
        "price_in_cents": 999900,  # ₹9,999
        "currency": "INR",
    },
    {
        "code": PlanTier.ENTERPRISE,
        "name": "Enterprise",
        "description": (
            "Unlimited / custom limits for large consultancies. "
            "NULL limits mean no cap."
        ),
        "max_branches": None,
        "max_staff": None,
        "max_students": None,
        "price_in_cents": 2499900,  # ₹24,999
        "currency": "INR",
    },
)


def seed_default_plans(session: Session) -> int:
    """Insert any missing plan catalog rows; return the count inserted.

    Re-running this on a populated catalog is a no-op (no row is
    updated, no duplicate is inserted). The function is the
    authoritative source of the default catalog -- the E9 task
    #105 Plan model is the *shape*; this function is the *content*.
    """
    existing_codes = {row.code for row in session.query(Plan.code).all()}
    now = datetime.now(timezone.utc)
    inserted = 0
    for entry in DEFAULT_PLANS:
        if entry["code"] in existing_codes:
            continue
        session.add(
            Plan(
                code=entry["code"],
                name=entry["name"],
                description=entry["description"],
                max_branches=entry["max_branches"],
                max_staff=entry["max_staff"],
                max_students=entry["max_students"],
                price_in_cents=entry["price_in_cents"],
                currency=entry["currency"],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        inserted += 1
    if inserted:
        session.commit()
    return inserted


def seed_default_plans_if_empty(session: Session) -> int:
    """Convenience wrapper used by the SQLite bootstrap hook.

    Equivalent to :func:`seed_default_plans` today (the function is
    already idempotent) but named so the boot path reads naturally
    alongside :func:`app.seed.runner.seed_demo_data_if_empty`.
    """
    return seed_default_plans(session)
