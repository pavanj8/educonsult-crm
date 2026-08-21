"""create notifications table

Revision ID: j3k4l5m6n7o8
Revises: d4440f78c1cb
Create Date: 2026-08-25 00:00:00.000000

Adds the ``notifications`` table for the E48 in-app notification
generation pipeline (Journey J41; issue #229 schema; #230 service
+ hooks; #231 tests). The table stores a tenant-scoped row per
in-app notification event with the minimum data the E50 read/mark-
read flow needs to render the notification center (event_type,
title, message, read_at, optional convenience FKs).

The ``user_id``/``related_application_id``/``related_document_id``/
``related_stage_history_id`` foreign keys use ``ON DELETE SET NULL``
so deleting the originating row does not cascade-delete the audit
record — the notification history is preserved.

A composite index on ``(tenant_id, user_id)`` accelerates the
primary read path (the E50 ``GET /notifications`` list-by-user
endpoint) and the unread-count query.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j3k4l5m6n7o8"
down_revision: Union[str, None] = "d4440f78c1cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.String(length=1024), nullable=False),
        sa.Column(
            "related_application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "related_document_id",
            sa.Integer(),
            sa.ForeignKey("student_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "related_stage_history_id",
            sa.Integer(),
            sa.ForeignKey("stage_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_tenant_id", "notifications", ["tenant_id"]
    )
    op.create_index(
        "ix_notifications_user_id", "notifications", ["user_id"]
    )
    op.create_index(
        "ix_notifications_event_type", "notifications", ["event_type"]
    )
    op.create_index(
        "ix_notifications_related_application_id",
        "notifications",
        ["related_application_id"],
    )
    op.create_index(
        "ix_notifications_tenant_user_unread",
        "notifications",
        ["tenant_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_tenant_user_unread", table_name="notifications"
    )
    op.drop_index(
        "ix_notifications_related_application_id", table_name="notifications"
    )
    op.drop_index("ix_notifications_event_type", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_tenant_id", table_name="notifications")
    op.drop_table("notifications")
