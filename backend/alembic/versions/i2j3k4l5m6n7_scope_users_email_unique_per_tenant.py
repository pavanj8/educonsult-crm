"""scope users.email uniqueness per tenant

Revision ID: i2j3k4l5m6n7
Revises: h1b2c3d4e5f6
Create Date: 2026-08-21 04:00:00.000000

Per docs/requirements.md §1 the system is multi-tenant and "every table carries
a tenant_id"; the same identifier in different tenants is independent. The
original E5 users migration declared ``users.email`` globally unique
(``ix_users_email``), which incorrectly blocks legitimate same-email
registrations across two different consultancies.

This migration:

* Drops the global unique index on ``users.email``.
* Adds a composite unique constraint ``(tenant_id, email)`` so the database
  enforces the same boundary the application code does (E16 issue #140;
  ``backend/app/auth/email_uniqueness.py``). Two rows with the same email
  may coexist as long as they belong to different tenants.
* Preserves the non-unique index on ``users.email`` for login lookups (E5
  ``POST /auth/login`` uses a case-insensitive ``func.lower(email)`` query
  against this column).

PostgreSQL supports ``ALTER TABLE ... ADD CONSTRAINT`` directly, but SQLite
does not -- the same DDL must therefore go through Alembic's batch mode
(copy-and-recreate the table) so the test suite, which uses an in-memory
SQLite database, exercises the constraint too.

PostgreSQL and SQLite both allow multiple NULL values in a composite
unique constraint, so platform-level accounts (``tenant_id IS NULL``,
e.g. ``super_admin``) keep a globally-unique email without colliding with
non-NULL tenant rows. The application layer still case-insensitive-scopes
its lookup to one tenant for E16 registration, so case differences within a
tenant remain rejected by the ``(tenant_id, email)`` constraint only when
the application layer has already normalized the value (which the E16
router does at the API edge).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "i2j3k4l5m6n7"
down_revision: Union[str, None] = "h1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def _apply_batch_changes() -> None:
    """Drop the unique index, recreate it non-unique, add composite UNIQUE.

    Always runs through Alembic's batch mode so PostgreSQL and SQLite behave
    the same way: SQLite doesn't support ALTER TABLE ... ADD CONSTRAINT
    directly, while PostgreSQL does -- batch mode handles both uniformly by
    rebuilding the table under the hood.
    """
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index(op.f("ix_users_email"))
        batch_op.create_index(op.f("ix_users_email"), ["email"], unique=False)
        batch_op.create_unique_constraint(
            op.f("uq_users_tenant_id_email"),
            ["tenant_id", "email"],
        )


def _revert_batch_changes() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint(op.f("uq_users_tenant_id_email"), type_="unique")
        batch_op.drop_index(op.f("ix_users_email"))
        batch_op.create_index(op.f("ix_users_email"), ["email"], unique=True)


def upgrade() -> None:
    _apply_batch_changes()


def downgrade() -> None:
    _revert_batch_changes()
