"""create applications table

Revision ID: f5e6a7b8c9d0
Revises: e5f6a7b8c9d0
Create Date: 2026-08-20 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5e6a7b8c9d0"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("university_id", sa.Integer(), nullable=True),
        sa.Column("program_id", sa.Integer(), nullable=True),
        sa.Column("assigned_counselor_id", sa.Integer(), nullable=True),
        sa.Column(
            "stage",
            sa.Enum(
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
                name="application_stage",
                native_enum=False,
                length=50,
            ),
            nullable=False,
            server_default="registered",
        ),
        sa.Column("student_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_applications_tenant_id"), "applications", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_applications_branch_id"), "applications", ["branch_id"], unique=False)
    op.create_index(op.f("ix_applications_student_id"), "applications", ["student_id"], unique=False)
    op.create_index(
        op.f("ix_applications_assigned_counselor_id"),
        "applications",
        ["assigned_counselor_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_applications_assigned_counselor_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_student_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_branch_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_tenant_id"), table_name="applications")
    op.drop_table("applications")
