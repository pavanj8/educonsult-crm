"""add branch_id and assigned_counselor_id to applications

Revision ID: g0b1c2d3e4f5
Revises: f8a9b0c1d2e3
Create Date: 2026-08-20 22:30:00.000000

E21 · Journey J14 (issue #156): Counselor views their assigned
student/application queue. The E21 ``GET /applications/assigned-to-me``
endpoint scopes by ``branch_id`` (every application lives in exactly one
branch) and filters by ``assigned_counselor_id`` (which counselor owns
the application; nullable until E19 auto-assignment runs).

Both columns are added as ``nullable=True`` for backwards compatibility
with applications created by the E18 ``POST /applications`` endpoint
(which did not yet capture either value). They will be back-filled and
constrained non-null in their respective epic tasks.

The ``applications.student_id`` foreign key is also tightened from the
implicit ``ON DELETE NO ACTION`` to ``ON DELETE CASCADE`` so that
deleting a STUDENT row drops their applications cleanly (matching the
ORM model in ``backend/app/models/application.py``). The
``assigned_counselor_id`` foreign key uses ``ON DELETE SET NULL`` so
deleting a counselor account un-assigns (rather than deletes) their
applications.

Note on SQLite support: SQLite does not support ALTER TABLE … DROP/ADD
CONSTRAINT, so the FK-rule changes are applied only on PostgreSQL.
``tests/conftest.py`` uses SQLite (``sqlite://:memory:``) with
``Base.metadata.create_all`` to materialise schema, which already
creates the columns and the new FK rules inline (the ORM model drives
that schema). Production runs target PostgreSQL where Alembic's
constraint manipulation is supported.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g0b1c2d3e4f5"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgresql(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Add the new columns. Both nullable for backwards compatibility with
    # rows already created by the E18 create_application endpoint (it does
    # not yet capture branch or counselor).
    op.add_column(
        "applications",
        sa.Column("branch_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_applications_branch_id"),
        "applications",
        ["branch_id"],
        unique=False,
    )

    op.add_column(
        "applications",
        sa.Column("assigned_counselor_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_applications_assigned_counselor_id"),
        "applications",
        ["assigned_counselor_id"],
        unique=False,
    )

    # 2) Tighten the existing student_id FK and add a new assigned_counselor_id
    # FK. On PostgreSQL we drop + recreate the student_id FK with ON DELETE
    # CASCADE and add assigned_counselor_id FK with ON DELETE SET NULL. On
    # SQLite (which doesn't support ALTER TABLE … DROP/ADD CONSTRAINT) we
    # only add the new assigned_counselor_id FK via a temporary table pattern
    # is overkill: the SQLite test path uses Base.metadata.create_all which
    # applies the ORM-declared FKs inline. The ORM model on SQLite picks up
    # the declared ondelete rule automatically.
    inspector = sa.inspect(bind)

    if _is_postgresql(bind):
        existing_student_fks = {
            fk["name"]
            for fk in inspector.get_foreign_keys("applications")
            if fk.get("constrained_columns") == ["student_id"]
            and fk.get("name") is not None
        }
        for fk_name in existing_student_fks:
            op.drop_constraint(fk_name, "applications", type_="foreignkey")

        op.create_foreign_key(
            "fk_applications_student_id_users",
            source_table="applications",
            referent_table="users",
            local_cols=["student_id"],
            remote_cols=["id"],
            ondelete="CASCADE",
        )

        op.create_foreign_key(
            "fk_applications_assigned_counselor_id_users",
            source_table="applications",
            referent_table="users",
            local_cols=["assigned_counselor_id"],
            remote_cols=["id"],
            ondelete="SET NULL",
        )
    else:
        # SQLite: production schema doesn't run this path (CI uses in-memory
        # SQLite via ``Base.metadata.create_all``), but keep the migration
        # idempotent and dialect-safe by skipping constraint rewrites. The
        # new column indexes above still go through.
        # The test suite (``tests/database/test_alembic.py``) runs
        # ``alembic upgrade head`` on a fresh SQLite DB; the FK rule change
        # is a no-op there and the columns + indexes are added cleanly.
        pass


def downgrade() -> None:
    bind = op.get_bind()

    if _is_postgresql(bind):
        op.drop_constraint(
            "fk_applications_assigned_counselor_id_users",
            "applications",
            type_="foreignkey",
        )
        op.drop_constraint(
            "fk_applications_student_id_users",
            "applications",
            type_="foreignkey",
        )
        # Re-create the original (no-ondelete) student_id FK.
        op.create_foreign_key(
            "fk_applications_student_id_users",
            source_table="applications",
            referent_table="users",
            local_cols=["student_id"],
            remote_cols=["id"],
        )

    op.drop_index(
        op.f("ix_applications_assigned_counselor_id"),
        table_name="applications",
    )
    op.drop_column("applications", "assigned_counselor_id")

    op.drop_index(op.f("ix_applications_branch_id"), table_name="applications")
    op.drop_column("applications", "branch_id")
