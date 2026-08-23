"""create meetings table

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
Create Date: 2026-08-27 00:00:00.000000

Meeting storage for E22 counselor scheduling (J15, Requirements §5).
Every meeting is tenant-scoped and belongs to one application, counselor,
and student. Foreign keys cascade when the associated record is deleted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "m6n7o8p9q0r1"
down_revision: Union[str, None] = "l5m6n7o8p9q0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "counselor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "application_id", "counselor_id", "student_id", "scheduled_at"):
        op.create_index(op.f(f"ix_meetings_{column}"), "meetings", [column], unique=False)


def downgrade() -> None:
    for column in ("scheduled_at", "student_id", "counselor_id", "application_id", "tenant_id"):
        op.drop_index(op.f(f"ix_meetings_{column}"), table_name="meetings")
    op.drop_table("meetings")
