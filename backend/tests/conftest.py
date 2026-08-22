from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.database as _database_module
import app.models  # noqa: F401 — register ORM models with Base.metadata
from app.db.database import get_db
from app.main import app
from app.models.base import Base
from app.rbac.dependencies import get_current_user
from app.rbac.user import AuthenticatedUser

TEST_DATABASE_URL = "sqlite://"

# The ORIGINAL database-module objects the routers + this conftest captured at
# import time. Some tests (tests/database/*) call importlib.reload(app.db.database),
# which rebinds these to NEW objects and leaks that mutation to every later test:
# get_db then no longer matches the object routers use, so dependency_overrides on
# get_db silently stop applying and tests fail depending on run order. Restoring
# after each test keeps the module identity stable and the suite order-independent
# (docs/adr/0029).
_ORIGINAL_DB_ATTRS = {
    "get_db": _database_module.get_db,
    "engine": _database_module.engine,
    "SessionLocal": _database_module.SessionLocal,
}


@pytest.fixture(autouse=True)
def _restore_database_module_after_reload() -> Generator[None, None, None]:
    yield
    for name, obj in _ORIGINAL_DB_ATTRS.items():
        setattr(_database_module, name, obj)


@pytest.fixture(autouse=True)
def _reset_rate_limiter_between_tests() -> Generator[None, None, None]:
    """Reset the in-process auth rate limiter between tests (E7; Journey J46).

    The limiter is a module-level singleton shared by every ``TestClient``
    boundary test (the ``client`` fixture reuses one ``FastAPI`` app
    instance for the lifetime of the session). Without this reset a
    test that legitimately trips the cap would leak its bucket into the
    next test, masking regressions / flaking unrelated tests. The reset
    runs *after* the test body so a test can observe the bucket before
    it is cleared.
    """
    yield
    from app.auth.rate_limit import reset_for_tests

    reset_for_tests()


def make_auth_headers(access_token: str = "test-access-token") -> dict[str, str]:
    """Return Authorization headers for API requests (JWT verification wired in E5)."""
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture()
def db_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine: Engine) -> Generator[TestClient, None, None]:
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return make_auth_headers()


@pytest.fixture()
def override_authenticated_user() -> Generator[Callable[[AuthenticatedUser], None], None, None]:
    """Override ``get_current_user`` for the duration of a test."""

    def _override(user: AuthenticatedUser) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    yield _override
    app.dependency_overrides.pop(get_current_user, None)
