"""create stage_transitions table

Revision ID: f7a8b9c0d1e2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


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

    # Seed platform-wide default transition rules via the canonical application
    # seeder. This keeps the migration and the runtime boot path in sync
    # (both rely on ``app.pipeline.default_transitions.seed_default_stage_transitions``)
    # and avoids dialect-specific raw SQL (e.g. ``datetime('now')`` is SQLite-only).
    # The seeder uses Python-side ``datetime.now(timezone.utc)`` so it works
    # identically on PostgreSQL and SQLite.
    from app.pipeline.default_transitions import seed_default_stage_transitions

    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        seed_default_stage_transitions(session)
    finally:
        session.close()


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