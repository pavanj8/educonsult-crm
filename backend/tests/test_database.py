from datetime import datetime, timezone

import pytest
from sqlalchemy import String, create_engine, inspect
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as database_module
from app.database import get_db
from app.models.base import Base, TenantScopedBase


class _SampleTenantModel(TenantScopedBase):
    __tablename__ = "test_tenant_scoped_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


@pytest.fixture()
def sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


def test_database_override_is_honored(monkeypatch):
    monkeypatch.setenv("DATABASE_OVERRIDE", "sqlite:///./override_test.db")
    import importlib

    importlib.reload(database_module)
    assert database_module.SQLALCHEMY_DATABASE_URL == "sqlite:///./override_test.db"


def test_default_database_url_uses_postgres_when_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_OVERRIDE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib

    importlib.reload(database_module)
    assert database_module.SQLALCHEMY_DATABASE_URL.startswith("postgresql")


def test_engine_connects(sqlite_engine):
    with sqlite_engine.connect() as connection:
        assert connection.dialect.name == "sqlite"


def test_get_db_yields_session_and_closes(monkeypatch, sqlite_engine):
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)
    closed: list[bool] = []
    original_close = test_session_local.class_.close

    def tracking_close(self):
        closed.append(True)
        return original_close(self)

    monkeypatch.setattr(test_session_local.class_, "close", tracking_close)
    monkeypatch.setattr(database_module, "SessionLocal", test_session_local)

    sessions = []
    for session in get_db():
        sessions.append(session)
        assert session.is_active

    assert len(sessions) == 1
    assert closed == [True]


def test_tenant_scoped_base_has_required_columns():
    mapper = inspect(_SampleTenantModel)
    column_names = {column.key for column in mapper.columns}
    assert column_names == {"id", "tenant_id", "created_at", "updated_at", "name"}


def test_tenant_scoped_model_persists_row(sqlite_engine):
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)
    now = datetime.now(timezone.utc)

    with testing_session_local() as session:
        row = _SampleTenantModel(tenant_id=42, name="demo", created_at=now, updated_at=now)
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.id is not None
        assert row.tenant_id == 42
        assert row.name == "demo"
