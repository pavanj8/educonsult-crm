"""create stage_history table

Revision ID: h1b2c3d4e5f6
Revises: g0b1c2d3e4f5
Create Date: 2026-08-21 00:00:00.000000

E25 (Application Stage Progression Engine) -- issue #169 advance-stage API
with history logging. The advance-stage endpoint appends one row per
successful transition to ``stage_history`` so the frontend stage timeline
(and any future audit/analytics view) can replay what happened.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "h1b2c3d4e5f6"
down_revision: str | None = "g0b1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Re-use the DB-level ENUM type created by f7a8b9c0d1e2. Using
        # create_type=False prevents Alembic from attempting to create a
        # second copy of the same enum, which would fail on PostgreSQL.
        stage_enum = sa.Enum(
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
        from_stage_type = stage_enum
        to_stage_type = stage_enum
    else:
        # SQLite stores as VARCHAR(50) via native_enum=False.
        stage_enum = sa.Enum(
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
        from_stage_type = stage_enum
        to_stage_type = stage_enum

    op.create_table(
        "stage_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_stage", from_stage_type, nullable=True),
        sa.Column("to_stage", to_stage_type, nullable=False),
        sa.Column(
            "changed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
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
