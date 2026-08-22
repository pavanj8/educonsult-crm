"""create password_reset_tokens table

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2026-08-25 00:00:00.000000

Adds the ``password_reset_tokens`` table backing the E6 password-reset
flow (Journey J45; Requirements §8: "JWT auth with refresh tokens";
"Forgot-password flow via emailed reset link/token").

Each row is a single-use token issued by ``POST /auth/forgot-password``
(issue #90) and consumed by ``POST /auth/reset-password`` (issue #91).

Design:

* ``tenant_id`` -- ADR-0001: every table carries ``tenant_id``.
* ``user_id`` FK -> ``users.id`` (ON DELETE CASCADE) -- the account
  that requested the reset. CASCADE so removing a user also removes
  any outstanding tokens (they can no longer be used anyway).
* ``token_hash`` stores a SHA-256 *hash* of the random token string,
  not the plaintext. The plaintext is only ever sent to the user's
  email; the database only ever sees the hash, so a DB leak does not
  expose live reset links (same hygiene as E5 refresh-token storage).
  Indexed and uniquely constrained because the reset endpoint will
  look rows up by hash.
* ``expires_at`` -- the deadline after which the token is invalid
  (default 1 hour from issue in the application layer). Indexed so a
  scheduled cleanup / "expired token" lookup stays fast.
* ``used_at`` -- nullable timestamp set when the token is consumed by
  ``POST /auth/reset-password``. NULL = not yet used. Indexed for the
  same reason as ``expires_at``.

Foreign keys are declared inline on CREATE TABLE so the migration
works on SQLite (which forbids ALTER TABLE + ADD CONSTRAINT).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k4l5m6n7o8p9"
down_revision: Union[str, None] = "j3k4l5m6n7o8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_tenant_id"),
        "password_reset_tokens",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"),
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_password_reset_tokens_token_hash"),
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_password_reset_tokens_expires_at"),
        "password_reset_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_password_reset_tokens_used_at"),
        "password_reset_tokens",
        ["used_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_password_reset_tokens_used_at"), table_name="password_reset_tokens"
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_expires_at"),
        table_name="password_reset_tokens",
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_token_hash"), table_name="password_reset_tokens"
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens"
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_tenant_id"), table_name="password_reset_tokens"
    )
    op.drop_table("password_reset_tokens")
