"""extend applications table with counselor queue + pipeline metadata

Revision ID: ab1c2d3e4f56
Revises: f8a9b0c1d2e3
Create Date: 2026-08-20 23:00:00.000000

Adds the columns required by the E21 counselor dashboard endpoint
(``GET /counselor/queue`` and ``GET /counselor/queue/counts``) on top of
the E18 baseline created by ``f6a7b8c9d0e1_create_applications_table``.

New columns:

* ``assigned_counselor_id`` (FK -> users.id, ON DELETE SET NULL) — the
  counselor that owns this application in the queue (nullable while the
  round-robin assignment in E19 has not yet run).
* ``target_university_id`` / ``target_program_id`` — denormalized
  university/program references kept alongside the E18 ``university_id``
  / ``program_id`` columns for the counselor queue filters. They were
  the names originally chosen for the E21 endpoints and are preserved
  to keep that contract stable.
* ``stage_reason`` — optional reason text captured when an application
  reaches a terminal stage (rejected / withdrawn) per Requirements §5.
* ``enrollment_date`` — date the application was marked Enrolled.
* ``loan_opted_in`` / ``loan_status`` / ``loan_lender`` / ``loan_amount``
  — loan tracking fields per Requirements §5 (Journeys J29/J30).

The corresponding indexes are added for the columns the queue queries
filter or join on (assigned_counselor_id, target_university_id,
target_program_id, stage).

Issue #157 (E21 frontend) carries this migration because the backend
deliverables for #156 (E21 backend) and #144 (E18 model) were already
landed without the columns E21 reads; closing the gap here keeps the
Postgres path consistent with what ``Base.metadata.create_all`` produces
on the SQLite test path.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ab1c2d3e4f56"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Loosen the E18 NOT NULL constraint on university_id/program_id so the
    # counselor queue fixtures (which create applications without picking a
    # university/program) can share the same model. The router-side
    # validators in ``POST /applications`` still reject unknown IDs.
    op.alter_column("applications", "university_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("applications", "program_id", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "applications",
        sa.Column("assigned_counselor_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("target_university_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("target_program_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("stage_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("enrollment_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("loan_opted_in", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "applications",
        sa.Column("loan_status", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("loan_lender", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("loan_amount", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_applications_assigned_counselor_id"),
        "applications",
        ["assigned_counselor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_applications_target_university_id"),
        "applications",
        ["target_university_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_applications_target_program_id"),
        "applications",
        ["target_program_id"],
        unique=False,
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
    op.drop_constraint(
        "fk_applications_assigned_counselor_id_users",
        "applications",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_applications_target_program_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_target_university_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_assigned_counselor_id"), table_name="applications")
    op.drop_column("applications", "loan_amount")
    op.drop_column("applications", "loan_lender")
    op.drop_column("applications", "loan_status")
    op.drop_column("applications", "loan_opted_in")
    op.drop_column("applications", "enrollment_date")
    op.drop_column("applications", "stage_reason")
    op.drop_column("applications", "target_program_id")
    op.drop_column("applications", "target_university_id")
    op.drop_column("applications", "assigned_counselor_id")
    # Restore the original NOT NULL constraint to match f6a7b8c9d0e1.
    op.alter_column("applications", "university_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("applications", "program_id", existing_type=sa.Integer(), nullable=False)