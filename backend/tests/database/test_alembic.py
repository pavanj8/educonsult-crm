import importlib
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

import app.db.database as database_module

BACKEND_DIR = Path(__file__).resolve().parents[2]
INITIAL_REVISION = "c119bac8fd8a"
HEAD_REVISION = "f8a9b0c1d2e3"


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
        assert "stage_transitions" in table_names
        assert "applications" in table_names
        assert "countries" in table_names
        assert "universities" in table_names
        assert "programs" in table_names
        user_columns = {column["name"] for column in inspect(connection).get_columns("users")}
        assert "is_active" in user_columns
        assert "name" in user_columns
        assert "phone" in user_columns
        assert "date_of_birth" in user_columns
        assert "target_country_id" in user_columns
        assert "target_university_id" in user_columns
        assert "target_program_id" in user_columns
        stage_columns = {column["name"] for column in inspect(connection).get_columns("stage_transitions")}
        assert "from_stage" in stage_columns
        assert "to_stage" in stage_columns
        assert "tenant_id" in stage_columns
        assert "is_active" in stage_columns
        assert "created_at" in stage_columns
        assert "updated_at" in stage_columns
        application_columns = {
            column["name"] for column in inspect(connection).get_columns("applications")
        }
        assert application_columns == {
            "id",
            "tenant_id",
            "student_id",
            "university_id",
            "program_id",
            "stage",
            "created_at",
            "updated_at",
        }


def test_alembic_upgrade_head_seeds_stage_transitions(tmp_path, monkeypatch):
    """After `alembic upgrade head`, the stage_transitions table contains the platform defaults."""
    db_path = tmp_path / "alembic_seed_test.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_OVERRIDE", database_url)
    importlib.reload(database_module)

    command.upgrade(_alembic_config(), "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT from_stage, to_stage, tenant_id, is_active "
                "FROM stage_transitions ORDER BY tenant_id, from_stage, to_stage"
            )
        ).fetchall()

    # All default rows must be present, active, and scoped to NULL tenant.
    seeded = {(r[0], r[1]): (r[2], bool(r[3])) for r in rows}
    from app.pipeline.default_transitions import DEFAULT_TRANSITIONS

    for from_stage, to_stage in DEFAULT_TRANSITIONS:
        assert (from_stage.value, to_stage.value) in seeded, (
            f"Missing default transition {from_stage.value} -> {to_stage.value}"
        )
        assert seeded[(from_stage.value, to_stage.value)] == (None, True)


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