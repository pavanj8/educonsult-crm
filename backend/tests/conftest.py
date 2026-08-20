from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register ORM models with Base.metadata
from app.db.database import get_db
from app.main import app
from app.models.base import Base
from app.rbac.dependencies import get_current_user
from app.rbac.user import AuthenticatedUser

TEST_DATABASE_URL = "sqlite://"


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
def client(db_engine: Engine, db_session: Session) -> Generator[TestClient, None, None]:
    """Test client that shares the SAME session as the test's db_session fixture.

    This ensures that data seeded by tests is visible to the app's request handlers.
    """

    def override_get_db() -> Generator[Session, None, None]:
        # Yield the SAME session instance that tests use so flushed/committed
        # data is immediately visible.
        try:
            yield db_session
        finally:
            pass

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


# Ensure the test counseling applications table is created alongside app models.
# Import it here so Base.metadata.create_all() (called in the db_engine fixture)

# Ensure the test counseling applications table is created alongside app models.
# Import it here so Base.metadata.create_all() (called in the db_engine fixture)
# creates the table in the SQLite in-memory DB.
from tests.counseling.helpers import _TestApplication  # noqa: F401
