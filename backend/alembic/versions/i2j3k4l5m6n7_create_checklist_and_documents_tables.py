"""create checklist_item_templates and student_documents tables

Revision ID: i2j3k4l5m6n7
Revises: h1b2c3d4e5f6
Create Date: 2026-08-22 01:00:00.000000

Adds the two tables that back the E26
``GET /applications/{application_id}/checklist`` endpoint ("merges
template + upload status", Journey J19) and the E27 student document
upload flow (Journey J20):

* ``checklist_item_templates`` — the per-stage/per-program *template*
  half. Defines which documents are required at which pipeline stage
  for which program (Requirements §5; E15 schema; J8). The full CRUD
  lands in a follow-up E15 ticket; this migration only creates the
  persisted shape.
* ``student_documents`` — the *upload status* half. Each row is a
  student's actual upload against a checklist item, with a
  ``status`` enum (pending / approved / rejected) capturing the
  verifier's decision. The full upload API and S3-compatible storage
  integration land in sibling tickets #175 / #176; this migration
  only creates the persisted shape required by issue #174 (E27 schema)
  and by E26's read-side merge.

The stage ENUM type is reused from ``stage`` (created by
``f7a8b9c0d1e2``); on PostgreSQL we pass ``create_type=False`` to
avoid colliding with the existing type. On SQLite we fall back to
VARCHAR(50) via ``native_enum=False``.

The student-document status ENUM is a brand-new ``student_document_status``
type on PostgreSQL and a VARCHAR(20) on SQLite.

Foreign keys are declared inline on CREATE TABLE so the migration
works on SQLite (which forbids ALTER TABLE + ADD CONSTRAINT).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "i2j3k4l5m6n7"
down_revision: Union[str, None] = "h1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _stage_column_type() -> sa.Enum:
    """Reuse the ``stage`` ENUM type created by ``f7a8b9c0d1e2``.

    PostgreSQL: ``create_type=False`` so we never collide with the
    existing type. SQLite: falls back to VARCHAR(50) via
    ``native_enum=False``.
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


def _student_document_status_column_type() -> sa.Enum:
    """Brand-new ``student_document_status`` ENUM (or VARCHAR(20) on SQLite)."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.Enum(
            "pending",
            "approved",
            "rejected",
            name="student_document_status",
        )
    return sa.Enum(
        "pending",
        "approved",
        "rejected",
        name="student_document_status",
        native_enum=False,
        length=20,
    )


def upgrade() -> None:
    stage_type = _stage_column_type()
    document_status_type = _student_document_status_column_type()

    op.create_table(
        "checklist_item_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("stage", stage_type, nullable=False),
        sa.Column(
            "program_id",
            sa.Integer(),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_checklist_item_templates_tenant_id"),
        "checklist_item_templates",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checklist_item_templates_stage"),
        "checklist_item_templates",
        ["stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checklist_item_templates_program_id"),
        "checklist_item_templates",
        ["program_id"],
        unique=False,
    )

    op.create_table(
        "student_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "checklist_item_template_id",
            sa.Integer(),
            sa.ForeignKey("checklist_item_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", document_status_type, nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column(
            "uploaded_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "verified_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_student_documents_tenant_id"),
        "student_documents",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_documents_application_id"),
        "student_documents",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_documents_checklist_item_template_id"),
        "student_documents",
        ["checklist_item_template_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_documents_status"),
        "student_documents",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_documents_uploaded_by_user_id"),
        "student_documents",
        ["uploaded_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_student_documents_uploaded_by_user_id"),
        table_name="student_documents",
    )
    op.drop_index(
        op.f("ix_student_documents_status"),
        table_name="student_documents",
    )
    op.drop_index(
        op.f("ix_student_documents_checklist_item_template_id"),
        table_name="student_documents",
    )
    op.drop_index(
        op.f("ix_student_documents_application_id"),
        table_name="student_documents",
    )
    op.drop_index(
        op.f("ix_student_documents_tenant_id"),
        table_name="student_documents",
    )
    op.drop_table("student_documents")

    op.drop_index(
        op.f("ix_checklist_item_templates_program_id"),
        table_name="checklist_item_templates",
    )
    op.drop_index(
        op.f("ix_checklist_item_templates_stage"),
        table_name="checklist_item_templates",
    )
    op.drop_index(
        op.f("ix_checklist_item_templates_tenant_id"),
        table_name="checklist_item_templates",
    )
    op.drop_table("checklist_item_templates")
