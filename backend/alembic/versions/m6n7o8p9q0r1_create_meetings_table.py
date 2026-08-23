"""create meetings table

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
Create Date: 2026-08-27 00:00:00.000000

Meeting storage for E22 counselor scheduling (J15, Requirements §5).
Every meeting is tenant-scoped and belongs to one application, counselor,
and student. Foreign keys cascade when the associated record is deleted.

Indexes:

* ``ix_meetings_application_id`` / ``ix_meetings_student_id`` /
  ``ix_meetings_scheduled_at`` -- single-column indexes for the
  ``GET /meetings?application_id=...&student_id=...`` list filters and
  the upcoming-meetings query ordered by ``scheduled_at`` (E23, J16).
* ``ix_meetings_tenant_counselor_scheduled`` -- composite index for
  the counselor's "my meetings" path (the dominant query from the
  E22 counselor dashboard, J15).

``duration_minutes`` carries a server-side default of 60 minutes to
match the ORM / Pydantic default so a future migration that adds
``Meeting(...)`` from a non-ORM path still gets a sensible value.
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
        sa.Column(
            "duration_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_meetings_tenant_id"),
        "meetings",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meetings_application_id"),
        "meetings",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meetings_student_id"),
        "meetings",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meetings_scheduled_at"),
        "meetings",
        ["scheduled_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meetings_tenant_counselor_scheduled"),
        "meetings",
        ["tenant_id", "counselor_id", "scheduled_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_meetings_tenant_counselor_scheduled"),
        table_name="meetings",
    )
    op.drop_index(op.f("ix_meetings_scheduled_at"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_student_id"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_application_id"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_tenant_id"), table_name="meetings")
    op.drop_table("meetings")
