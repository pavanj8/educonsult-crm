import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.rbac import Permission, Role
from app.rbac.dependencies import get_current_user, require_permission, require_role
from app.rbac.user import AuthenticatedUser


@pytest.fixture
def rbac_test_app() -> FastAPI:
    app = FastAPI()

    @app.get("/role-protected")
    def role_protected(
        user: AuthenticatedUser = Depends(require_role(Role.COUNSELOR)),
    ) -> dict[str, str]:
        return {"role": user.role}

    @app.get("/multi-role-protected")
    def multi_role_protected(
        user: AuthenticatedUser = Depends(
            require_role(Role.CONSULTANCY_OWNER, Role.BRANCH_MANAGER)
        ),
    ) -> dict[str, str]:
        return {"role": user.role}

    @app.get("/permission-protected")
    def permission_protected(
        user: AuthenticatedUser = Depends(require_permission(Permission.STAFF_CREATE)),
    ) -> dict[str, str]:
        return {"role": user.role}

    return app


@pytest.fixture
def client(rbac_test_app: FastAPI) -> TestClient:
    return TestClient(rbac_test_app)


def _override_user(rbac_test_app: FastAPI, user: AuthenticatedUser) -> None:
    rbac_test_app.dependency_overrides[get_current_user] = lambda: user


def test_get_current_user_raises_401_when_not_overridden(client: TestClient) -> None:
    response = client.get("/role-protected")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_require_role_allows_matching_role(
    rbac_test_app: FastAPI, client: TestClient
) -> None:
    _override_user(
        rbac_test_app,
        AuthenticatedUser(id=1, role=Role.COUNSELOR, tenant_id=1, branch_id=1),
    )
    response = client.get("/role-protected")
    assert response.status_code == 200
    assert response.json() == {"role": "counselor"}


def test_require_role_denies_non_matching_role(
    rbac_test_app: FastAPI, client: TestClient
) -> None:
    _override_user(
        rbac_test_app,
        AuthenticatedUser(id=2, role=Role.STUDENT, tenant_id=1, branch_id=1),
    )
    response = client.get("/role-protected")
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role"


def test_require_role_accepts_any_of_multiple_allowed_roles(
    rbac_test_app: FastAPI, client: TestClient
) -> None:
    _override_user(
        rbac_test_app,
        AuthenticatedUser(id=3, role=Role.BRANCH_MANAGER, tenant_id=1, branch_id=1),
    )
    response = client.get("/multi-role-protected")
    assert response.status_code == 200
    assert response.json() == {"role": "branch_manager"}


def test_require_permission_allows_when_role_has_permission(
    rbac_test_app: FastAPI, client: TestClient
) -> None:
    _override_user(
        rbac_test_app,
        AuthenticatedUser(id=4, role=Role.CONSULTANCY_OWNER, tenant_id=1),
    )
    response = client.get("/permission-protected")
    assert response.status_code == 200
    assert response.json() == {"role": "consultancy_owner"}


def test_require_permission_denies_when_role_lacks_permission(
    rbac_test_app: FastAPI, client: TestClient
) -> None:
    _override_user(
        rbac_test_app,
        AuthenticatedUser(id=5, role=Role.STUDENT, tenant_id=1),
    )
    response = client.get("/permission-protected")
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
