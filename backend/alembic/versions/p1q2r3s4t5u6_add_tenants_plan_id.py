"""add tenants.plan_id foreign key

Revision ID: p1q2r3s4t5u6
Revises: o8p9q0r1s2t3
Create Date: 2026-09-16 00:00:00.000000

Adds the ``plan_id`` nullable FK column on ``tenants`` for E9 task
#107's per-tier usage limit enforcement (branches / staff /
students). The column points at the platform-level ``plans`` catalog
created by ``o8p9q0r1s2t3_create_plans_table`` (E9 task #105) and is
written by the super-admin assign/change-plan API owned by E9 task
#106.

The column is nullable so a brand-new tenant exists with no assigned
plan until the Super Admin explicitly picks one; the enforcement
helper :func:`app.services.plan_limits.get_tenant_plan` treats
``NULL`` as "no plan assigned, do not enforce limits", which means
existing tenants created before a plan was assigned continue to
create branches / staff / students without errors. ON DELETE RESTRICT
matches the catalog row's lifecycle -- an active tier cannot be
removed while tenants still point at it.

No data backfill is included because every existing tenant row has
``plan_id = NULL`` by definition (the column is being introduced in
this migration). Operators wanting a default plan can run a one-off
``UPDATE`` after this migration; that decision is left to the
platform operator because "default plan" is a business policy, not a
schema concern.

Implementation note: SQLite (used by the test suite via
``DATABASE_OVERRIDE=sqlite://``) does not support ``ALTER TABLE ...
ADD CONSTRAINT``, so the column, index, and FK are added together
inside :func:`op.batch_alter_table`. On PostgreSQL the batch-mode
helper is a no-op and the operations translate to plain ``ALTER
TABLE`` statements -- there is no behavioral difference at runtime.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, Sequence[str], None] = "o8p9q0r1s2t3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tenants", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("plan_id", sa.Integer(), nullable=True),
        )
        batch_op.create_index(
            op.f("ix_tenants_plan_id"),
            ["plan_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_tenants_plan_id_plans",
            "plans",
            ["plan_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("tenants", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_tenants_plan_id_plans", type_="foreignkey")
        batch_op.drop_index(op.f("ix_tenants_plan_id"))
        batch_op.drop_column("plan_id")