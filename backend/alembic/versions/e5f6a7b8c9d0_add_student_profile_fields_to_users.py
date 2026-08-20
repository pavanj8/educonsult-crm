"""add student profile fields to users

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-19 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("target_country_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("target_university_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("target_program_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_users_target_country_id"), "users", ["target_country_id"], unique=False)
    op.create_index(op.f("ix_users_target_university_id"), "users", ["target_university_id"], unique=False)
    op.create_index(op.f("ix_users_target_program_id"), "users", ["target_program_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_target_program_id"), table_name="users")
    op.drop_index(op.f("ix_users_target_university_id"), table_name="users")
    op.drop_index(op.f("ix_users_target_country_id"), table_name="users")
    op.drop_column("users", "target_program_id")
    op.drop_column("users", "target_university_id")
    op.drop_column("users", "target_country_id")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "phone")
    op.drop_column("users", "name")
