"""create visa_outcomes table

Revision ID: r1s2t3u4v5w6
Revises: q9r0s1t2u3v4
Create Date: 2026-09-26 00:00:00.000000

E35 task #195 (Journey J28 "Visa Processor updates visa
outcome/status"; Requirements §3 Visa Processor role + §5 Student
Journey & Data Model). Adds the ``visa_outcomes`` table the E35
backend API ticket (#195) reads and writes against, and the E32
document-review-notification / E48 notification story can hook into.

* ``visa_outcomes`` -- one row per application whose pipeline stage
  is ``visa_processing`` (the outcome is a property of *the*
  application at the visa stage, not a list of historical entries).
  Tenant-scoped (ADR-0001).

  * ``application_id`` -- 1:1 FK to ``applications`` (ON DELETE
    CASCADE so removing an application also clears its visa
    outcome). UNIQUE so a single application carries at most one
    visa outcome row, matching J28's phrasing of "Visa Processor
    updates visa outcome/status".
  * ``status`` -- short ``String(32)`` label for the recorded
    outcome (e.g. ``approved``, ``rejected``, ``pending``). Modelled
    as a short string rather than a Postgres ENUM so the catalogue
    can grow without an Alembic data migration; the Python-side
    Pydantic schema ``UpdateVisaOutcomeRequest`` is the contract.
    A 32-char ceiling is comfortably larger than the realistic
    label set (e.g. "approved", "rejected", "withdrawn").
  * ``outcome_date`` -- timezone-aware ``DateTime`` for when the
    outcome was recorded (J28). Nullable so a draft / pre-decision
    outcome can be saved without committing to an "outcome date".
  * ``notes`` -- optional free-text notes the visa processor
    captured alongside the outcome (e.g. embassy comments). Mirrors
    the text / length of the ``MarkRejectedRequest.reason`` ceiling
    from the E39 follow-up.

Indexes target the primary access pattern: per-application lookup
(the E35 update endpoint hydrates by application id; the visa queue
rows may JOIN on this to surface outcome status alongside each
queue row, mirroring the E34 visa detail join pattern).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r1s2t3u4v5w6"
down_revision: Union[str, None] = "q9r0s1t2u3v4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visa_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("outcome_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_visa_outcomes_application_id"),
    )
    op.create_index(
        op.f("ix_visa_outcomes_tenant_id"),
        "visa_outcomes",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_visa_outcomes_application_id"),
        "visa_outcomes",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_visa_outcomes_application_id"), table_name="visa_outcomes")
    op.drop_index(op.f("ix_visa_outcomes_tenant_id"), table_name="visa_outcomes")
    op.drop_table("visa_outcomes")
