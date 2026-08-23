"""create notes table

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
Create Date: 2026-09-01 00:00:00.000000

Internal counseling notes for E24 (Journey J17; Requirements §5:
"Internal notes: Staff-only comment thread per student
(counselor/verifier/branch manager visible), hidden from student").

This migration only owns the persisted shape. The CRUD API and the
student-isolation visibility check land in the sibling E24 task
#165; this migration makes the table, columns, and indexes available
so the API can be wired up against it.

* ``notes`` -- one row per staff-authored note attached to a
  student (and optionally to one of the student's applications).
  Tenant-scoped (ADR-0001). The author is the staff user who wrote
  the note; the API in #165 is what enforces that the author is not
  a student. The student FK and the application FK both cascade on
  delete so cleanup of a student (or an application) also clears
  their internal notes.

Indexes target the two primary access patterns:

* ``ix_notes_student_id`` -- the J17 thread list scoped to a student
  (the dominant read pattern, by student).
* ``ix_notes_application_id`` -- the E24 frontend notes-thread UI on
  the application detail view (#166) lists notes by application.
* ``ix_notes_author_user_id`` -- audit / "notes I authored" lookups
  (Requirements §8 audit trail).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n7o8p9q0r1s2"
down_revision: Union[str, None] = "m6n7o8p9q0r1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "author_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notes_tenant_id"),
        "notes",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notes_student_id"),
        "notes",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notes_application_id"),
        "notes",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notes_author_user_id"),
        "notes",
        ["author_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notes_author_user_id"), table_name="notes")
    op.drop_index(op.f("ix_notes_application_id"), table_name="notes")
    op.drop_index(op.f("ix_notes_student_id"), table_name="notes")
    op.drop_index(op.f("ix_notes_tenant_id"), table_name="notes")
    op.drop_table("notes")