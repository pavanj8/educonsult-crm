"""POST /applications endpoint tests (E18, Journey J11, issue #145)."""

from app.auth import create_access_token
from app.db.database import get_db
from app.main import app
from app.models.application import Application
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def make_create_application_payload(
    *,
    university_id: int = 101,
    program_id: int = 201,
) -> dict:
    return {
        "university_id": university_id,
        "program_id": program_id,
    }


def _seed_student(db_session, tenant_id: int, branch_id: int):
    return make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_id,
        branch_id=branch_id,
        email="student@example.test",
    )


def test_create_application_success(client, db_session, override_authenticated_user):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/applications",
        json=make_create_application_payload(university_id=42, program_id=99),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == tenant.id
    assert body["student_id"] == student.id
    assert body["university_id"] == 42
    assert body["program_id"] == 99
    assert body["stage"] == PipelineStage.REGISTERED.value
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


def test_create_application_persists_row(client, db_session, override_authenticated_user):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/applications",
        json=make_create_application_payload(),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201
    application = db_session.get(Application, response.json()["id"])
    assert application is not None
    assert application.student_id == student.id
    assert application.tenant_id == tenant.id
    assert application.stage == PipelineStage.REGISTERED


def test_create_application_allows_multiple_per_student(
    client,
    db_session,
    override_authenticated_user,
):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )
    headers = {"Authorization": "Bearer test-token"}

    first = client.post(
        "/applications",
        json=make_create_application_payload(university_id=1, program_id=10),
        headers=headers,
    )
    second = client.post(
        "/applications",
        json=make_create_application_payload(university_id=2, program_id=20),
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["university_id"] == 1
    assert second.json()["university_id"] == 2


def test_create_application_requires_authentication(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    _seed_student(db_session, tenant.id, branch.id)

    response = client.post(
        "/applications",
        json=make_create_application_payload(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_create_application_rejects_non_student_role(
    client,
    db_session,
    override_authenticated_user,
):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/applications",
        json=make_create_application_payload(),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_create_application_rejects_deactivated_student(
    client,
    db_session,
    override_authenticated_user,
):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        is_active=False,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/applications",
        json=make_create_application_payload(),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is deactivated"


def test_create_application_rejects_missing_university_id(
    client,
    db_session,
    override_authenticated_user,
):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/applications",
        json={"program_id": 201},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_create_application_rejects_invalid_ids(
    client,
    db_session,
    override_authenticated_user,
):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/applications",
        json={"university_id": 0, "program_id": 0},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_create_application_success_with_real_jwt(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    password = "student-password"
    make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="student.jwt@example.test",
        password=password,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "student.jwt@example.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.post(
        "/applications",
        headers=make_auth_headers(access_token),
        json=make_create_application_payload(university_id=55, program_id=66),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["university_id"] == 55
    assert body["program_id"] == 66
    assert body["stage"] == PipelineStage.REGISTERED.value
    assert body["tenant_id"] == tenant.id


def test_create_application_rejects_invalid_access_token(client):
    response = client.post(
        "/applications",
        headers=make_auth_headers("not-a-valid-jwt"),
        json=make_create_application_payload(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_create_application_rejects_non_student_jwt(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    token = create_access_token(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/applications",
        headers=make_auth_headers(token),
        json=make_create_application_payload(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_create_application_rejects_missing_program_id(
    client,
    db_session,
    override_authenticated_user,
):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/applications",
        json={"university_id": 101},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_create_application_rejects_student_missing_tenant_scope(
    client,
    db_session,
    override_authenticated_user,
):
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=None,
        branch_id=1,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=None,
            branch_id=1,
        )
    )

    response = client.post(
        "/applications",
        json=make_create_application_payload(),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Student account is missing tenant scope"


def test_create_application_returns_503_when_database_unavailable_on_user_lookup(
    client,
    db_session,
    override_authenticated_user,
):
    """OperationalError in _get_active_student → db.get() returns 503."""
    from unittest.mock import MagicMock
    from sqlalchemy.exc import OperationalError

    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)

    # Override auth so we reach _get_active_student without a valid JWT.
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    # Mock the DB session to raise OperationalError on get().
    mock_session = MagicMock()
    mock_session.get.side_effect = OperationalError(
        "stmt", {}, Exception("no such table")
    )

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/applications",
            headers={"Authorization": "Bearer test-token"},
            json={"university_id": 1, "program_id": 2},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Application service is temporarily unavailable"


def test_create_application_returns_503_when_database_unavailable_on_commit(
    client,
    db_session,
    override_authenticated_user,
):
    """OperationalError in db.commit() returns 503."""
    from unittest.mock import MagicMock
    from sqlalchemy.exc import OperationalError

    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)

    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    # Mock the DB session so get() returns the real student but commit() raises.
    mock_session = MagicMock()
    mock_session.get.return_value = student
    mock_session.commit.side_effect = OperationalError(
        "stmt", {}, Exception("disk full")
    )

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/applications",
            headers={"Authorization": "Bearer test-token"},
            json={"university_id": 1, "program_id": 2},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Application service is temporarily unavailable"


def test_create_application_tenant_id_matches_callers_tenant(
    client,
    db_session,
    override_authenticated_user,
):
    """The response tenant_id is always the caller's tenant, never another tenant's.

    This is a structural property: tenant_id is derived from the DB row inside
    _get_active_student, not from the request payload.  We assert it explicitly
    here to harden the cross-tenant isolation property at the API layer.
    """
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)

    student_a = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        email="student.tenant.a@example.test",
    )
    make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        email="student.tenant.b@example.test",
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student_a.id,
            tenant_id=tenant_a.id,
            branch_id=branch_a.id,
        )
    )

    response = client.post(
        "/applications",
        json={"university_id": 1, "program_id": 2},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201
    assert response.json()["tenant_id"] == tenant_a.id
    assert response.json()["tenant_id"] != tenant_b.id
