"""create plans table

Revision ID: o8p9q0r1s2t3
Revises: 9abd2b26ef086ede
Create Date: 2026-09-15 00:00:00.000000

Platform-level subscription plan catalog (E9 task #105; Journey J2;
Requirements §4 Billing & Subscription). One row per tier -- Starter /
Growth / Enterprise -- with per-tier limits consumed by the E9 task
#107 usage limit enforcement checks and by the J38 owner plan-usage
view (E45).

The catalog lives on its own ``plans`` table (no ``tenant_id`` column
on the row; plans are platform-global) per the ADR-0001 exception for
cross-tenant reference data. The future ``tenants.plan_id`` FK -- owned
by E9 task #106 -- is what makes a tenant point at a plan; this
<<<<<<< HEAD
migration only stands up the catalog and seeds the three rows so
``tenants.plan_id`` can resolve cleanly as soon as the FK lands.
=======
migration only stands up the catalog (no rows seeded here). Inserting
the three canonical tier rows is the platform seed / admin path's
responsibility (E9 task #106 / #108), which deliberately lives outside
the migration so it can be re-run idempotently and so re-seeding a
catalog row doesn't have to ship as a schema migration.
>>>>>>> origin/main

Columns:

* ``code`` -- stable PlanTier string (``STARTER`` / ``GROWTH`` /
<<<<<<< HEAD
  ``ENTERPRISE``); unique + indexed so duplicate seed runs can't
  double-insert the same tier and lookups by code are fast.
=======
  ``ENTERPRISE``); unique so duplicate seed runs can't double-insert
  the same tier. PostgreSQL materializes a unique index to back the
  ``UniqueConstraint``, which is what ``tenants.plan_id`` lookups
  and the future ``Plan`` API in #106 will key off -- no separate
  non-unique index is added on top.
>>>>>>> origin/main
* ``name`` -- human-readable display name ("Starter", "Growth",
  "Enterprise").
* ``description`` -- optional blurb shown on the J38 owner plan-usage
  page and the J39 Razorpay checkout.
* ``max_branches`` / ``max_staff`` / ``max_students`` -- per-tier caps
  consumed by E9 task #107. Nullable on purpose so Enterprise can
  advertise "unlimited" (Requirements §4) without picking a magic
  sentinel; the enforcement layer treats NULL as "no cap".
* ``is_active`` -- whether the tier is currently sellable; retired
  tiers stay in the table so historical ``tenants.plan_id`` rows
  remain readable.
* ``created_at`` / ``updated_at`` -- standard audit timestamps,
  matching the convention used on every other model in the repo.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o8p9q0r1s2t3"
down_revision: Union[str, None] = "9abd2b26ef086ede"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("max_branches", sa.Integer(), nullable=True),
        sa.Column("max_staff", sa.Integer(), nullable=True),
        sa.Column("max_students", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )
<<<<<<< HEAD
    op.create_index(
        op.f("ix_plans_code"),
        "plans",
        ["code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_plans_code"), table_name="plans")
=======


def downgrade() -> None:
>>>>>>> origin/main
    op.drop_table("plans")
