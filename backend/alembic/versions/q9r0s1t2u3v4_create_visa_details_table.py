"""create visa_details table

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-09-25 00:00:00.000000

E34 task #193 (Journey J27 "Visa Processor records visa type &
embassy interview date"; Requirements §3 Visa Processor role + §5
Student Journey & Data Model). Adds the ``visa_details`` table that
the E34 frontend ticket (#194) and a sibling backend API ticket
will read and write against.

* ``visa_details`` -- one row per application whose pipeline stage
  is ``visa_processing``. Tenant-scoped (ADR-0001).

  * ``application_id`` -- 1:1 FK to ``applications`` (ON DELETE
    CASCADE so removing an application also clears its visa
    detail). UNIQUE so a single application carries at most one
    visa detail row, matching J27's phrasing of "the visa type and
    interview date for the application" rather than a list of
    historical entries.
  * ``visa_type`` -- short ``String(100)`` label for the recorded
    visa type (e.g. "F-1 Student", "Tier 4 Student"). Modelled as
    free-form text rather than an enum because the spec does not
    promise an admin-managed master list of visa types in v1
    (master data in J7 covers countries / universities / programs).
    The frontend visa detail form (#194) can source a dropdown from
    E14 master data later without a schema change.
  * ``interview_date`` -- timezone-aware ``DateTime`` for the
    embassy interview date (J27). Nullable so the visa processor
    can record the visa type ahead of the interview date; the two
    fields are entered separately over time, not atomically.

  Outcome fields (status / outcome_date / notes) are intentionally
  NOT added here -- they belong to E35 (Visa Outcome Update;
  Journey J28) so that ticket owns its own schema decisions.

Indexes target the two access patterns the E33 visa queue (#191)
and the E34 update form (#194) need:

* ``ix_visa_details_tenant_id`` -- ADR-0001 tenant scoping; the
  primary tenant filter.
* ``ix_visa_details_application_id`` -- lookup by application (the
  E34 update form hydrates by application id; the E33 queue may
  JOIN on this to surface visa type / interview date alongside
  each queue row).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "q9r0s1t2u3v4"
down_revision: Union[str, None] = "p8q9r0s1t2u3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visa_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("visa_type", sa.String(length=100), nullable=False),
        sa.Column("interview_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_visa_details_application_id"),
    )
    op.create_index(
        op.f("ix_visa_details_tenant_id"),
        "visa_details",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_visa_details_application_id"),
        "visa_details",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_visa_details_application_id"), table_name="visa_details")
    op.drop_index(op.f("ix_visa_details_tenant_id"), table_name="visa_details")
    op.drop_table("visa_details")