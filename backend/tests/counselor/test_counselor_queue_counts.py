"""GET /counselor/queue/counts endpoint tests (E21; Journey J14)."""

from app.models.application import PipelineStage
from app.rbac.roles import Role
from tests.counselor.helpers import seed_application
from tests.factories.users import make_authenticated_user, make_db_user


def _seed_counselor(db_session, *, email: str = "counselor@example.test", tenant_id: int = 1) -> int:
    user = make_db_user(db_session, Role.COUNSELOR, email=email, tenant_id=tenant_id, branch_id=1)
    return user.id


def _seed_student(db_session, *, email: str = "student@example.test", tenant_id: int = 1) -> int:
    user = make_db_user(db_session, Role.STUDENT, email=email, tenant_id=tenant_id, branch_id=1)
    return user.id


def test_queue_counts_returns_stage_distribution(client, db_session, override_authenticated_user):
    """Counts endpoint returns the number of applications per stage."""
    counselor = _seed_counselor(db_session)
    student1 = _seed_student(db_session, email="s1@example.test")
    student2 = _seed_student(db_session, email="s2@example.test")
    student3 = _seed_student(db_session, email="s3@example.test")

    seed_application(db_session, student_id=student1, assigned_counselor_id=counselor, stage=PipelineStage.REGISTERED)
    seed_application(db_session, student_id=student2, assigned_counselor_id=counselor, stage=PipelineStage.REGISTERED)
    seed_application(db_session, student_id=student3, assigned_counselor_id=counselor, stage=PipelineStage.COUNSELING)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue/counts")

    assert response.status_code == 200
    data = response.json()
    assert data["registered"] == 2
    assert data["counseling"] == 1


def test_queue_counts_excludes_other_counselors_applications(client, db_session, override_authenticated_user):
    """Counts only include applications assigned to this counselor."""
    counselor = _seed_counselor(db_session)
    other_counselor = _seed_counselor(db_session, email="other@example.test")
    student1 = _seed_student(db_session, email="s1@example.test")
    student2 = _seed_student(db_session, email="s2@example.test")

    seed_application(db_session, student_id=student1, assigned_counselor_id=counselor, stage=PipelineStage.REGISTERED)
    seed_application(db_session, student_id=student2, assigned_counselor_id=other_counselor, stage=PipelineStage.REGISTERED)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue/counts")

    assert response.status_code == 200
    data = response.json()
    assert data["registered"] == 1


def test_queue_counts_returns_empty_for_no_applications(client, db_session, override_authenticated_user):
    """Counselor with no applications gets empty counts."""
    counselor = _seed_counselor(db_session)
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue/counts")

    assert response.status_code == 200
    assert response.json() == {}


def test_queue_counts_requires_authentication(client):
    """Unauthenticated requests are rejected."""
    response = client.get("/counselor/queue/counts")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_queue_counts_requires_permission(client, db_session, override_authenticated_user):
    """Users without APPLICATION_READ_ASSIGNED permission are rejected."""
    student = _seed_student(db_session)
    override_authenticated_user(make_authenticated_user(Role.STUDENT, user_id=student))

    response = client.get("/counselor/queue/counts")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
