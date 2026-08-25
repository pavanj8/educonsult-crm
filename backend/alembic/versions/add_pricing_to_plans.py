"""add pricing to plans

Revision ID: u4v5w6x7y8z9
Revises: t3u4v5w6x7y8
Create Date: 2026-12-15 00:00:00.000000

Add pricing columns to the plans table to support Razorpay checkout
for plan upgrades/downgrades (E46 task #222; Journey J39).

The three subscription tiers (Starter/Growth/Enterprise) each need a
price_in_cents stored in the plan catalog so the Razorpay order creation
endpoint (future E46 task #223) can read the target tier's price and
create an order for that amount. Price is stored in paisa (cents for
USD-like currencies, but Razorpay uses paisa for INR which is our
home market per Requirements §1).

Columns:

* ``price_in_cents`` -- price in smallest currency unit (paisa for INR,
  cents for USD). Required and non-nullable because every tier must have
  a published price for checkout. Integer to avoid floating-point issues.
* ``currency`` -- ISO 4217 currency code (default "INR" for the home
  market). Required so future multi-currency support is possible without
  a migration.

This migration also backfills the three existing plan rows with default
prices ( Starter: ₹4999, Growth: ₹9999, Enterprise: ₹24999 ) so the
catalog is ready for the E46 Razorpay checkout endpoints.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import table, column

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "u4v5w6x7y8z9"
down_revision: str | None = "t3u4v5w6x7y8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add the pricing columns
    op.add_column("plans", sa.Column("price_in_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("plans", sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"))

    # Backfill existing plan rows with default prices (in paisa)
    # Starter: ₹4999 = 499900 paisa
    # Growth: ₹9999 = 999900 paisa
    # Enterprise: ₹24999 = 2499900 paisa
    plans_table = table("plans",
        column("code", sa.String),
        column("price_in_cents", sa.Integer),
        column("currency", sa.String),
    )

    op.execute(
        plans_table.update()
        .where(plans_table.c.code == "starter")
        .values(price_in_cents=499900, currency="INR")
    )
    op.execute(
        plans_table.update()
        .where(plans_table.c.code == "growth")
        .values(price_in_cents=999900, currency="INR")
    )
    op.execute(
        plans_table.update()
        .where(plans_table.c.code == "enterprise")
        .values(price_in_cents=2499900, currency="INR")
    )


def downgrade() -> None:
    op.drop_column("plans", "currency")
    op.drop_column("plans", "price_in_cents")
