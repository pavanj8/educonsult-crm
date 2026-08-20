"""add branch_id and assigned_counselor_id to applications

Revision ID: g0b1c2d3e4f5
Revises: f8a9b0c1d2e3
Create Date: 2026-08-20 22:30:00.000000

The E18-created columns remain nullable for backwards compatibility. PostgreSQL
foreign-key delete rules are updated here, matching the ORM declarations.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "g0b1c2d3e4f5"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _student_foreign_key_name(bind: sa.Connection) -> str:
    inspector = sa.inspect(bind)
    for constraint in inspector.get_foreign_keys("applications"):
        if constraint.get("constrained_columns") == ["student_id"]:
            name = constraint.get("name")
            if name is not None:
                return name
    raise RuntimeError("applications.student_id foreign key constraint was not found")


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "applications",
        sa.Column("branch_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_applications_branch_id"),
        "applications",
        ["branch_id"],
        unique=False,
    )
    op.add_column(
        "applications",
        sa.Column("assigned_counselor_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_applications_assigned_counselor_id"),
        "applications",
        ["assigned_counselor_id"],
        unique=False,
    )

    if bind.dialect.name == "postgresql":
        op.drop_constraint(
            _student_foreign_key_name(bind),
            "applications",
            type_="foreignkey",
        )
        op.create_foreign_key(
            "fk_applications_student_id_users",
            "applications",
            "users",
            ["student_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_foreign_key(
            "fk_applications_assigned_counselor_id_users",
            "applications",
            "users",
            ["assigned_counselor_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(
            "fk_applications_assigned_counselor_id_users",
            "applications",
            type_="foreignkey",
        )
        op.drop_constraint(
            "fk_applications_student_id_users",
            "applications",
            type_="foreignkey",
        )
        op.create_foreign_key(
            "fk_applications_student_id_users",
            "applications",
            "users",
            ["student_id"],
            ["id"],
        )

    op.drop_index(
        op.f("ix_applications_assigned_counselor_id"),
        table_name="applications",
    )
    op.drop_column("applications", "assigned_counselor_id")
    op.drop_index(op.f("ix_applications_branch_id"), table_name="applications")
    op.drop_column("applications", "branch_id")
