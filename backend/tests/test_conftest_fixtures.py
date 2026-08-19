from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.main import app
from app.models.base import TenantScopedBase
from app.rbac import Role
from app.rbac.dependencies import get_current_user
from app.rbac.user import AuthenticatedUser
from tests.conftest import make_auth_headers


class _FixtureProbeModel(TenantScopedBase):
    __tablename__ = "test_conftest_probe_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


def test_make_auth_headers_returns_bearer_format() -> None:
    headers = make_auth_headers("my-token")
    assert headers == {"Authorization": "Bearer my-token"}


def test_auth_headers_fixture(auth_headers: dict[str, str]) -> None:
    assert auth_headers["Authorization"] == "Bearer test-access-token"


def test_db_session_fixture_persists_rows(db_session) -> None:
    now = datetime.now(timezone.utc)
    row = _FixtureProbeModel(tenant_id=1, name="probe", created_at=now, updated_at=now)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert row.id is not None
    assert row.name == "probe"


def test_client_fixture_hits_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_override_authenticated_user_sets_dependency(override_authenticated_user) -> None:
    user = AuthenticatedUser(id=1, role=Role.COUNSELOR, tenant_id=1, branch_id=1)
    override_authenticated_user(user)
    assert app.dependency_overrides[get_current_user]() == user
