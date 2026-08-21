"""create notifications table

Revision ID: j3k4l5m6n7o8
Revises: d4440f78c1cb
Create Date: 2026-08-24 02:00:00.000000

Adds the ``notifications`` table backing the E48 in-app notification
flow (Journey J41; Requirements §6 "In-app + email for status
changes, document verification results, meeting scheduling"). Each
row is a single in-app notification delivered to one user on a
relevant event.

The notification-creation service + event hooks that *populate* this
table land in the sibling E48 task; this migration owns the schema
only.

Design (Requirements §6; Journey J41; Epic E48):

* ``tenant_id`` -- ADR-0001: every table carries ``tenant_id``.
* ``user_id`` FK -> ``users.id`` (ON DELETE CASCADE) -- the recipient.
  A user without an account has no inbox, so deletion cascades.
* ``title`` / ``message`` -- the short heading and body shown in the
  notification center UI (frontend ``Notification.title`` /
  ``Notification.message``).
* ``read_at`` -- nullable timestamp set when the user marks the
  notification read (Journey J43). NULL = unread.
* ``application_id`` FK -> ``applications.id`` (ON DELETE SET NULL) --
  optional deep-link to the related application. Nullable because
  not every event is tied to an application.

Foreign keys are declared inline on CREATE TABLE so the migration
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
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
    op.create_index(
        op.f("ix_notifications_read_at"),
        "notifications",
        ["read_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_application_id"),
        "notifications",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notifications_application_id"),
        table_name="notifications",
    )
    op.drop_index(
        op.f("ix_notifications_read_at"),
        table_name="notifications",
    )
    op.drop_index(
        op.f("ix_notifications_user_id"),
        table_name="notifications",
    )
    op.drop_index(
        op.f("ix_notifications_tenant_id"),
        table_name="notifications",
    )
    op.drop_table("notifications")