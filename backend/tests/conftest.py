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
from app.rate_limit import RateLimiter, set_default_rate_limiter
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
def _reset_rate_limiter() -> Generator[None, None, None]:
    """Each test sees a fresh rate-limit bucket registry.

    The auth router (login / register-student / forgot-password) shares a
    process-wide :class:`RateLimiter` instance. Without resetting it,
    any test that fires more than the per-scope limit in a single process
    lifetime would start tripping 429s and masking the real assertion.
    The very-few rate-limit tests that need a *populated* registry opt
    in by replacing the singleton again inside their own body.
    """
    set_default_rate_limiter(RateLimiter())
    yield
    set_default_rate_limiter(None)


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
