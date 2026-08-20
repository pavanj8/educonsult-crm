"""create applications table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-20 03:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_applications_tenant_id"), "applications", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_applications_student_id"), "applications", ["student_id"], unique=False)
    op.create_index(
        op.f("ix_applications_university_id"), "applications", ["university_id"], unique=False
    )
    op.create_index(op.f("ix_applications_program_id"), "applications", ["program_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_applications_program_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_university_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_student_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_tenant_id"), table_name="applications")
    op.drop_table("applications")
