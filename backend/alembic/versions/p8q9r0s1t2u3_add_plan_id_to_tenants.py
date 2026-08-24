"""add plan_id FK to tenants

Revision ID: p8q9r0s1t2u3
Revises: o8p9q0r1s2t3
Create Date: 2026-09-20 00:00:00.000000

E9 task #106 (Journey J2; Requirements §4 Billing & Subscription).
Adds the nullable ``tenants.plan_id`` foreign key that points a
tenant at one of the platform-level catalog rows from the
``plans`` table (E9 task #105). Nullable so a brand-new tenant
exists with no plan assigned until the Super Admin explicitly
picks one via ``POST /tenants/{id}/plan``.

ON DELETE RESTRICT is intentional: a tier with active tenants
referencing it cannot be removed (the catalog ``is_active`` flag
is the supported retirement path). The column is indexed because
the cross-tenant ``GET /tenants`` list (super admin) and the
future J40 super-admin billing-status view (E47) both filter /
join on it.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "p8q9r0s1t2u3"
down_revision: Union[str, None] = "o8p9q0r1s2t3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "tenants",
        sa.Column("plan_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_tenants_plan_id"),
        "tenants",
        ["plan_id"],
        unique=False,
    )
    if bind.dialect.name == "postgresql":
        op.create_foreign_key(
            "fk_tenants_plan_id_plans",
            source_table="tenants",
            referent_table="plans",
            local_cols=["plan_id"],
            remote_cols=["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(
            "fk_tenants_plan_id_plans", "tenants", type_="foreignkey"
        )
    op.drop_index(op.f("ix_tenants_plan_id"), table_name="tenants")
    op.drop_column("tenants", "plan_id")
