"""add loan_opt_in to applications

Revision ID: s2t3u4v5w6x7
Revises: r1s2t3u4v5w6
Create Date: 2026-09-27 00:00:00.000000

E36 task #198 (Journey J29 "Student opts into loan tracking on an
application"; Requirements §5 "Loans: Tracking-only fields (opted-in,
status, amount, lender) — no separate loan officer workflow for v1").
Adds the boolean ``loan_opt_in`` column to ``applications``.

* NOT NULL with a server-side default of ``FALSE`` so existing rows
  pre-dating this migration persist cleanly without a backfill step
  (every pre-existing row effectively "did not opt in" -- the
  conservative default for the tracking flag).
* Mirrors the ORM declaration on :class:`app.models.application.Application`.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "s2t3u4v5w6x7"
down_revision: str | None = "r1s2t3u4v5w6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column(
            "loan_opt_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("applications", "loan_opt_in")
