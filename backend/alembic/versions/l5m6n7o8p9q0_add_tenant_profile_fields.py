"""add tenant profile fields (logo_url, brand_color, currency)

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2026-08-26 00:00:00.000000

Adds the three tenant-profile / branding columns required by E10 task
#109 (Journey J3; Requirements §1 White-labeling + Currency):

* ``tenants.logo_url`` -- nullable VARCHAR(2048) for the S3/MinIO URL
  uploaded via the E10 task #111 logo upload endpoint. Nullable
  because new tenants are seeded before any logo is provided.
* ``tenants.brand_color`` -- nullable VARCHAR(7) ``#RRGGBB`` string
  consumed by the E10 task #113 frontend theming.
* ``tenants.currency`` -- NOT NULL VARCHAR(3) ISO 4217 code, server
  default ``'INR'`` because the home market is India. Existing rows
  receive the default via the ``server_default`` on backfill.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "l5m6n7o8p9q0"
down_revision: Union[str, None] = "k4l5m6n7o8p9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("logo_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("brand_color", sa.String(length=7), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="INR",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "currency")
    op.drop_column("tenants", "brand_color")
    op.drop_column("tenants", "logo_url")