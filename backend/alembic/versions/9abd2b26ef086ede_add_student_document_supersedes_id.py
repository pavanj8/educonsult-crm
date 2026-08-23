"""add student_documents.supersedes_id column

Revision ID: 9abd2b26ef086ede
Revises: n7o8p9q0r1s2
Create Date: 2026-08-25 01:00:00.000000

Adds the ``supersedes_id`` self-FK column on ``student_documents`` for
the E31 ``POST /applications/{application_id}/documents`` re-upload
flow (issue #187; Journey J24: "Student re-uploads a rejected
document"). The link turns a re-upload from "yet another pending row"
into a versioned replacement with a preserved audit trail
(Requirements §8 — audit log on key actions such as document
approvals), so the previously-rejected row stays in the table with
its original ``status='rejected'`` and ``rejection_reason``.

The column is nullable so existing rows (and every initial upload,
which has no predecessor) keep working without backfill. ON DELETE
SET NULL is intentional: deleting one row must not cascade-delete the
re-upload that replaced it (an admin action on a single row must not
destroy the next version's audit chain). No other column changes are
made; the upload router's existing validation plus a new
``supersedes_document_id`` form-field handler will populate the column
on the re-upload path only.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9abd2b26ef086ede"
down_revision: Union[str, None] = "n7o8p9q0r1s2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "student_documents",
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_student_documents_supersedes_id"),
        "student_documents",
        ["supersedes_id"],
        unique=False,
    )
    if bind.dialect.name == "postgresql":
        op.create_foreign_key(
            op.f("fk_student_documents_supersedes_id_student_documents"),
            "student_documents",
            "student_documents",
            ["supersedes_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(
            op.f("fk_student_documents_supersedes_id_student_documents"),
            "student_documents",
            type_="foreignkey",
        )
    op.drop_index(
        op.f("ix_student_documents_supersedes_id"),
        table_name="student_documents",
    )
    op.drop_column("student_documents", "supersedes_id")