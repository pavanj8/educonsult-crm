"""create notifications table

Revision ID: j3k4l5m6n7o8
Revises: d4440f78c1cb
Create Date: 2026-08-25 01:00:00.000000

Adds the ``notifications`` table backing the E50 notification center
list / mark-read API (issue #236; Journey J43). It is the read-side
of the notification surface; the generation half (E48; Journey J41)
hooks into this table from a sibling ticket.

Each row is a single in-app notification addressed to one user:

* ``tenant_id`` is denormalised alongside ``user_id`` for index-scan
  tenant scoping (ADR-0001).
* ``user_id`` FKs ``users.id`` with ON DELETE CASCADE so removing a
  user cleans up their in-app inbox (the audit trail lives elsewhere
  -- e.g. ``stage_history`` -- and is independent of this table).
* ``title`` / ``message`` are the human-readable strings surfaced
  verbatim by the notification center UI (the frontend's
  ``Notification`` type mirrors this shape verbatim).
* ``read_at`` is NULL until the recipient first marks the row read
  (Requirements §6: "User views notification center and marks items
  read"). The list API counts ``read_at IS NULL`` for the
  ``unread_count`` summary field.

Foreign keys are declared inline on the CREATE TABLE so the migration
works on SQLite (which forbids ALTER TABLE + ADD CONSTRAINT).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "j3k4l5m6n7o8"
down_revision: Union[str, None] = "d4440f78c1cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notifications_tenant_id"),
        "notifications",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_user_id"),
        "notifications",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notifications_user_id"),
        table_name="notifications",
    )
    op.drop_index(
        op.f("ix_notifications_tenant_id"),
        table_name="notifications",
    )
    op.drop_table("notifications")