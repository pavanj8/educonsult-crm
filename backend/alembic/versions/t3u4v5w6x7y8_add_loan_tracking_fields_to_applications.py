"""add loan_status / loan_lender / loan_amount to applications

Revision ID: t3u4v5w6x7y8
Revises: s2t3u4v5w6x7
Create Date: 2026-09-28 00:00:00.000000

E37 task #200 (Journey J30 "Staff records/updates loan status, lender,
amount"; Requirements §5 "Loans: Tracking-only fields (opted-in,
status, amount, lender) — no separate loan officer workflow for v1").
Adds three tracking-only columns to ``applications`` so staff can
record the loan status, lender, and amount via the update-loan-status
API:

* ``loan_status`` -- short ``String(32)`` label for the recorded loan
  status (e.g. ``"in_progress"``, ``"approved"``, ``"rejected"``). Free
  text so the catalogue can grow without an Alembic data migration;
  the Pydantic schema on the update API is the contract.
* ``loan_lender`` -- short ``String(120)`` label for the lender
  (e.g. "HDFC Credila", "SBI Scholar"). Free text because the spec
  does not promise an admin-managed master list of lenders in v1
  (master data in J7 covers countries / universities / programs).
* ``loan_amount`` -- ``Numeric(12, 2)`` for the loan amount in the
  tenant's display currency. ``NUMERIC(12, 2)`` matches the
  ``Numeric`` precision used for tenant financial fields elsewhere on
  the platform and is comfortable for the realistic loan-amount range
  (up to ~9.99B in the chosen currency unit). ``nullable=True`` so
  staff can record the status / lender first and the amount later, or
  clear a previously-recorded amount.

All three columns are nullable so existing rows pre-dating this
migration persist cleanly (the previous E36 ``loan_opt_in`` migration
sets the conservative default of "did not opt in"; the new tracking
columns here default to "no value recorded yet"). The E37 update API
applies the loan fields only when the caller supplies a value, so an
explicit ``null`` in a PATCH body clears the field rather than
silently persisting a stale value.

Mirrors the ORM declaration on :class:`app.models.application.Application`.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "t3u4v5w6x7y8"
down_revision: str | None = "s2t3u4v5w6x7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("loan_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("loan_lender", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("loan_amount", sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "loan_amount")
    op.drop_column("applications", "loan_lender")
    op.drop_column("applications", "loan_status")
