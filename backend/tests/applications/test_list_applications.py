"""GET /applications list endpoint tests (E18, Journey J11, issue #146)."""

from app.auth import create_access_token
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


def _seed_student(db_session, tenant_id: int, branch_id: int, *, email: str = "student@example.test"):
    return make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_id,
        branch_id=branch_id,
        email=email,
    )


def _seed_application(
    db_session,
    *,
    tenant_id: int,
    student_id: int,
    university_id: int,
    program_id: int,
    stage: PipelineStage = PipelineStage.REGISTERED,
) -> Application:
    application = Application(
        tenant_id=tenant_id,
        student_id=student_id,
        university_id=university_id,
        program_id=program_id,
        stage=stage,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application


def test_list_applications_returns_own_applications(client, db_session, override_authenticated_user):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)
    first = _seed_application(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        university_id=101,
        program_id=201,
    )
    second = _seed_application(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        university_id=102,
        program_id=202,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.get(
        "/applications",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] == first.id
    assert body[1]["id"] == second.id
    assert body[0]["student_id"] == student.id
    assert body[1]["student_id"] == student.id
    assert body[0]["university_id"] == 101
    assert body[1]["university_id"] == 102
    assert body[0]["stage"] == PipelineStage.REGISTERED.value
    assert body[1]["stage"] == PipelineStage.COUNSELING.value


def test_list_applications_empty_when_none(client, db_session, override_authenticated_user):
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

    response = client.get(
        "/applications",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_applications_excludes_other_students(
    client,
    db_session,
    override_authenticated_user,
):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id, email="student-a@example.test")
    other_student = _seed_student(
        db_session,
        tenant.id,
        branch.id,
        email="student-b@example.test",
    )
    own = _seed_application(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        university_id=101,
        program_id=201,
    )
    _seed_application(
        db_session,
        tenant_id=tenant.id,
        student_id=other_student.id,
        university_id=999,
        program_id=888,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.get(
        "/applications",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == own.id
    assert body[0]["university_id"] == 101


def test_list_applications_requires_authentication(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _seed_student(db_session, tenant.id, branch.id)
    _seed_application(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        university_id=101,
        program_id=201,
    )

    response = client.get("/applications")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_list_applications_rejects_non_student_role(
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

    response = client.get(
        "/applications",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_list_applications_rejects_deactivated_student(
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

    response = client.get(
        "/applications",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is deactivated"


def test_list_applications_rejects_student_missing_tenant_scope(
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

    response = client.get(
        "/applications",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Student account is missing tenant scope"


def test_list_applications_success_with_real_jwt(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    password = "student-password"
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="student.jwt@example.test",
        password=password,
    )
    _seed_application(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        university_id=55,
        program_id=66,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "student.jwt@example.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.get(
        "/applications",
        headers=make_auth_headers(access_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["university_id"] == 55
    assert body[0]["program_id"] == 66
    assert body[0]["student_id"] == student.id


def test_list_applications_rejects_invalid_access_token(client):
    response = client.get(
        "/applications",
        headers=make_auth_headers("not-a-valid-jwt"),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_list_applications_excludes_other_tenant_applications(
    client,
    db_session,
    override_authenticated_user,
):
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id, name="Branch A")
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id, name="Branch B")
    student_a = _seed_student(
        db_session,
        tenant_a.id,
        branch_a.id,
        email="student-a@example.test",
    )
    student_b = _seed_student(
        db_session,
        tenant_b.id,
        branch_b.id,
        email="student-b@example.test",
    )
    own = _seed_application(
        db_session,
        tenant_id=tenant_a.id,
        student_id=student_a.id,
        university_id=101,
        program_id=201,
    )
    _seed_application(
        db_session,
        tenant_id=tenant_b.id,
        student_id=student_b.id,
        university_id=999,
        program_id=888,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student_a.id,
            tenant_id=tenant_a.id,
            branch_id=branch_a.id,
        )
    )

    response = client.get(
        "/applications",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == own.id
    assert body[0]["tenant_id"] == tenant_a.id


def test_list_applications_rejects_non_student_jwt(client, db_session):
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

    response = client.get(
        "/applications",
        headers=make_auth_headers(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
