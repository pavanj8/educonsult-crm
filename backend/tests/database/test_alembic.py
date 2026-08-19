import importlib
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

import app.db.database as database_module

BACKEND_DIR = Path(__file__).resolve().parents[2]
INITIAL_REVISION = "c119bac8fd8a"
HEAD_REVISION = "b2c3d4e5f6a7"


def _alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def test_alembic_scaffold_files_exist():
    assert (BACKEND_DIR / "alembic.ini").is_file()
    assert (BACKEND_DIR / "alembic" / "env.py").is_file()
    assert (BACKEND_DIR / "alembic" / "script.py.mako").is_file()


def test_initial_migration_is_empty():
    migration_path = (
        BACKEND_DIR / "alembic" / "versions" / f"{INITIAL_REVISION}_initial_empty_migration.py"
    )
    content = migration_path.read_text()

    assert migration_path.is_file()
    assert "def upgrade()" in content
    assert "def downgrade()" in content
    assert "op.create_table" not in content
    assert "op.drop_table" not in content


def test_alembic_upgrade_head_records_revision(tmp_path, monkeypatch):
    db_path = tmp_path / "alembic_test.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_OVERRIDE", database_url)
    importlib.reload(database_module)

    command.upgrade(_alembic_config(), "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert "alembic_version" in inspect(connection).get_table_names()
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == HEAD_REVISION
        table_names = inspect(connection).get_table_names()
        assert "users" in table_names
        assert "tenants" in table_names
        assert "branches" in table_names


def test_alembic_downgrade_base_clears_revision(tmp_path, monkeypatch):
    db_path = tmp_path / "alembic_test.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_OVERRIDE", database_url)
    importlib.reload(database_module)

    config = _alembic_config()
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        assert version is None
