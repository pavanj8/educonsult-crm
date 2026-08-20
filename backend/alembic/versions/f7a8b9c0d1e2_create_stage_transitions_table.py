"""create stage_transitions table

Revision ID: f7a8b9c0d1e2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the Stage enum type in the database (PostgreSQL only; SQLite ignores enums).
    # On PostgreSQL this creates a DB-level ENUM type. On SQLite it is a no-op.
    # Dialect-specific creation is handled via checkfirst to avoid errors.
    if op.get_bind().dialect.name == "postgresql":
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
        )
        stage_enum.create(op.get_bind(), checkfirst=True)
        # Use native_enum so PostgreSQL uses the ENUM type.
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

    # Foreign key is declared inline so it is part of CREATE TABLE,
    # avoiding SQLite's restriction on ALTER TABLE + ADD CONSTRAINT.
    op.create_table(
        "stage_transitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_stage", from_stage_type, nullable=False),
        sa.Column("to_stage", to_stage_type, nullable=False),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.UniqueConstraint("from_stage", "to_stage", "tenant_id", name="uq_stage_transition"),
    )

    op.create_index(
        op.f("ix_stage_transitions_tenant_id"),
        "stage_transitions",
        ["tenant_id"],
        unique=False,
    )

    # Seed platform-wide default transition rules (no tenant_id).
    # Forward pipeline progression: REGISTERED → ... → VISA_PROCESSING → ENROLLED
    # LOAN_PROCESSING can be entered from VISA_PROCESSING and returns to it.
    default_transitions = [
        # Normal forward progression
        ("registered", "counseling"),
        ("counseling", "university_shortlisting"),
        ("university_shortlisting", "application_submitted"),
        ("application_submitted", "document_verification"),
        ("document_verification", "offer_letter"),
        ("offer_letter", "visa_processing"),
        ("visa_processing", "enrolled"),
        # Loan processing loop (optional, entered from visa_processing, returns to it)
        ("visa_processing", "loan_processing"),
        ("loan_processing", "visa_processing"),
        # Terminal states can be reached from most non-terminal stages
        ("registered", "rejected"),
        ("registered", "withdrawn"),
        ("counseling", "rejected"),
        ("counseling", "withdrawn"),
        ("university_shortlisting", "rejected"),
        ("university_shortlisting", "withdrawn"),
        ("application_submitted", "rejected"),
        ("application_submitted", "withdrawn"),
        ("document_verification", "rejected"),
        ("document_verification", "withdrawn"),
        ("offer_letter", "rejected"),
        ("offer_letter", "withdrawn"),
        ("visa_processing", "rejected"),
        ("visa_processing", "withdrawn"),
        ("loan_processing", "rejected"),
        ("loan_processing", "withdrawn"),
    ]

    op.execute(
        "INSERT INTO stage_transitions "
        "(from_stage, to_stage, tenant_id, is_active, created_at, updated_at) "
        "VALUES " + ", ".join(
            f"('{frm}', '{to}', NULL, true, datetime('now'), datetime('now'))"
            for frm, to in default_transitions
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_stage_transitions_tenant_id"),
        table_name="stage_transitions",
    )
    op.drop_table("stage_transitions")
    # On PostgreSQL the DB-level ENUM type persists after table drop;
    # SQLAlchemy/Alembic 2.x does not provide a portable cross-dialect
    # DROP TYPE via op.execute() that works on both PostgreSQL and SQLite.
    # The next upgrade's checkfirst=True is a no-op when the type already exists.
