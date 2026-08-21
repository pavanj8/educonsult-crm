"""add student_documents.approval_comment column

Revision ID: d4440f78c1cb
Revises: i2j3k4l5m6n7
Create Date: 2026-08-24 01:00:00.000000

Adds the ``approval_comment`` text column on ``student_documents`` for
the E29 ``POST /verifier/documents/{document_id}/approve`` endpoint
(issue #181; Journey J22). It is the approve-side counterpart of the
already-existing ``rejection_reason`` column: it lets a document
verifier record an optional free-text note when approving a student
upload (Requirements §5: "verifier approves/rejects with comments").

The column is nullable so existing rows (and an approve with no
comment) keep working without backfill. No other column changes are
made; ``status``, ``verified_by_user_id``, and ``verified_at`` are
already populated by the approve endpoint and need no migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4440f78c1cb"
down_revision: Union[str, None] = "i2j3k4l5m6n7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "student_documents",
        sa.Column("approval_comment", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("student_documents", "approval_comment")