"""create stage_history table

Revision ID: h1b2c3d4e5f6
Revises: g0b1c2d3e4f5
Create Date: 2026-08-21 02:00:00.000000

Adds the per-application stage-history audit log (E25; Journey J18).
Each row records one stage transition for an application (from_stage
-> to_stage), who performed it, when, and an optional reason.

The stage ENUM type is created dialect-aware:
  * PostgreSQL: a true DB-level ENUM named ``stage`` is created (and
    reused -- the same type is already in use by ``stage_transitions``
    and ``applications``).
  * SQLite: stages are stored as VARCHAR(50) via ``native_enum=False``
    -- SQLite ignores DB-level ENUM types entirely.

Foreign keys are declared inline on the CREATE TABLE so the migration
works on SQLite (which forbids ALTER TABLE + ADD CONSTRAINT).

This migration is the schema-only half of the E25 StageHistory task;
the runtime ``advance-stage`` API that writes rows here lands in a
follow-up E25 ticket.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "h1b2c3d4e5f6"
down_revision: Union[str, None] = "g0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _stage_column_type() -> sa.Enum:
    """Return a stage-enum column type appropriate for the current dialect.

    Reuses the stage ENUM type created by the ``f7a8b9c0d1e2``
    migration on PostgreSQL (``create_type=False`` so we never
    collide with an existing type). On SQLite we fall back to
    VARCHAR(50) via ``native_enum=False``.
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.Enum(
            "registered",
            "counseling",
            "university_shortlisting",
            "application_submitted",
            "document_verification",
            "offer_letter",
            "visa_processing",
            "loan_processing",
            "enrolled",
            "rejected",
            "withdrawn",
            name="stage",
            create_type=False,
        )
    return sa.Enum(
        "registered",
        "counseling",
        "university_shortlisting",
        "application_submitted",
        "document_verification",
        "offer_letter",
        "visa_processing",
        "loan_processing",
        "enrolled",
        "rejected",
        "withdrawn",
        name="stage",
        native_enum=False,
        length=50,
    )


def upgrade() -> None:
    stage_type = _stage_column_type()

    op.create_table(
        "stage_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_stage", stage_type, nullable=True),
        sa.Column("to_stage", stage_type, nullable=False),
        sa.Column(
            "changed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_stage_history_tenant_id"),
        "stage_history",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stage_history_application_id"),
        "stage_history",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stage_history_changed_by_user_id"),
        "stage_history",
        ["changed_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_stage_history_changed_by_user_id"),
        table_name="stage_history",
    )
    op.drop_index(
        op.f("ix_stage_history_application_id"),
        table_name="stage_history",
    )
    op.drop_index(
        op.f("ix_stage_history_tenant_id"),
        table_name="stage_history",
    )
    op.drop_table("stage_history")
