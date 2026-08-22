"""add tenant branding fields

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2026-08-26 00:00:00.000000

Adds the three white-labeling columns to ``tenants`` backing the E10
``PATCH /tenants/{id}/branding`` endpoint (Journey J3; Requirements §1:
"Each tenant can upload a logo + set a primary brand color"; E52
currency configuration). All three columns are nullable so the schema
remains compatible with existing tenants created before branding was a
concern.

* ``logo_url`` -- String(2048); long enough for a signed S3/MinIO URL.
  Set by the logo-upload endpoint (separate E10 ticket #111).
* ``brand_color`` -- String(7); canonical CSS hex form ``#RRGGBB``.
* ``currency`` -- String(3); ISO 4217 three-letter uppercase code,
  normalised by ``app.i18n.currency.normalize_currency_code``.

All columns are added without a server-side default so existing tenants
  simply read back ``NULL`` until their owner first sets them, which is
  the correct semantic for "no branding configured yet" (Requirements §1
  white-labeling).
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
        sa.Column("currency", sa.String(length=3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "currency")
    op.drop_column("tenants", "brand_color")
    op.drop_column("tenants", "logo_url")