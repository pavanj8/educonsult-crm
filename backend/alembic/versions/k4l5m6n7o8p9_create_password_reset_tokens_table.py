"""create password_reset_tokens table

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2026-08-25 00:00:00.000000

Adds the ``password_reset_tokens`` table backing the E6 password-reset
flow ("forgot-password flow via emailed reset link/token"; Journey
J45; Requirements §8). Each row is a single-use reset token issued
for one user.

The ``POST /auth/forgot-password`` endpoint that *issues* a token
(sibling ticket #90) writes here; the ``POST /auth/reset-password``
endpoint that *consumes* a token (sibling ticket #91) reads here.
This migration owns the schema only.

Design (Requirements §8; Journey J45; Epic E6):

* ``tenant_id`` -- ADR-0001: every table carries ``tenant_id``.
  Denormalised from the owning user so the reset endpoint can apply
  the standard tenant-scoping filter without a join to ``users``.
* ``user_id`` FK -> ``users.id`` (ON DELETE CASCADE) -- the recipient.
  Deleting a user account also drops any pending reset tokens for
  them (a user with no account has no inbox and no pending resets).
* ``token_hash`` -- the SHA-256 hex digest of the random reset token,
  *not* the raw token itself. The raw token is emailed to the user
  (E6 email template, sibling ticket #92) and never written to disk;
  only its hash is stored so a database leak does not expose usable
  reset links. 64 chars (hex of 32 bytes); unique-indexed because
  the reset endpoint's hot path is "look up token by its hash".
* ``expires_at`` -- the absolute deadline after which the token is
  rejected (Journey J45; the E6 tests cover "expired token" via this
  column). Indexed for the cleanup query "find all expired, unused
  tokens".
* ``used_at`` -- nullable timestamp set when the token is consumed
  by the reset endpoint. NULL = unused. Combined with the
  lookup-by-hash query, ``used_at IS NULL AND expires_at > now()``
  is the canonical "valid token" predicate, and a non-NULL value
  enforces single-use (the reset endpoint refuses a token whose
  ``used_at`` is already set, the second half of the E6
  "expired/invalid token" test scenarios).

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
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
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
        op.f("ix_password_reset_tokens_expires_at"),
        "password_reset_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_password_reset_tokens_expires_at"),
        table_name="password_reset_tokens",
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_user_id"),
        table_name="password_reset_tokens",
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_tenant_id"),
        table_name="password_reset_tokens",
    )
    op.drop_table("password_reset_tokens")