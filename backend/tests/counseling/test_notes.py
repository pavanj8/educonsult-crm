"""Tests for the /notes CRUD endpoints (E24; Journey J17; #165).

Covers:

* POST /notes (create)
  - 201 happy path: counselor (assigned), branch manager, consultancy
    owner, super admin, document verifier / receptionist blocked (no
    NOTE_CREATE permission)
  - 404 cross-tenant student
  - 404 missing student
  - 422 student-mismatch on application_id
  - 404 missing / cross-tenant application
  - 403 cross-branch for counselor + branch manager
  - 403 counselor not assigned to student
  - 422 validation (blank body, zero/negative ids, missing fields)
  - 401 missing auth
  - 503 on OperationalError during commit
* GET /notes (list)
  - counselor only sees notes for assigned students
  - branch manager sees branch-scoped notes
  - consultancy owner sees all in tenant
  - super admin sees all (no tenant filter)
  - document verifier / receptionist read-only behavior
  - student (no NOTE_READ) is rejected
  - cross-tenant returns empty
  - filter by student_id / application_id
  - 403 cross-tenant / cross-branch student_id probe
  - 422 zero ids
  - 401 missing auth
* GET /notes/{id} (single)
  - 200 happy path (each staff role)
  - 404 cross-tenant
  - 403 cross-branch for BM
  - 403 counselor not assigned
  - 401 missing auth
* PATCH /notes/{id} (update)
  - 200 happy path (author)
  - 404 missing / cross-tenant
  - 403 cross-branch for BM
  - 403 non-author (peer counselor / branch manager / owner)
  - 403 student / verifier / receptionist blocked (no NOTE_UPDATE)
  - 422 blank body
  - 401 missing auth
* DELETE /notes/{id}
  - 204 happy path (author)
  - 404 missing / cross-tenant
  - 403 non-author
  - 403 cross-branch for BM
  - 403 student / verifier / receptionist blocked (no NOTE_DELETE)
  - 401 missing auth
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.main import app
from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.counseling.note_helpers import seed_note
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _create_tenant(
    db_session: Session, *, name: str = "EduConsult Test", slug: str = "educonsult"
) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _auth_for(user: Any) -> Any:
    return make_authenticated_user(
        user.role,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


def _auth_super_admin(user: Any) -> Any:
    return make_authenticated_user(
        Role.SUPER_ADMIN,
        user_id=user.id,
        tenant_id=None,
        branch_id=None,
    )


def _auth_consultancy_owner(user: Any) -> Any:
    return make_authenticated_user(
        Role.CONSULTANCY_OWNER,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=None,
    )


def _note_payload(
    *,
    student_id: int,
    body: str = "Counselor note body",
    application_id: int | None = None,
) -> dict:
    payload: dict = {"student_id": student_id, "body": body}
    if application_id is not None:
        payload["application_id"] = application_id
    return payload


# ---------------------------------------------------------------------------
# POST /notes -- happy paths (per role)
# ---------------------------------------------------------------------------


def test_counselor_creates_note_for_assigned_student(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student.id, body="Needs visa follow-up"),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["student_id"] == student.id
    assert body["author_user_id"] == counselor.id
    assert body["tenant_id"] == tenant.id
    assert body["application_id"] is None
    assert body["body"] == "Needs visa follow-up"


def test_counselor_creates_note_with_application_anchor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(
            student_id=student.id, body="Anchored to application", application_id=application.id
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["application_id"] == application.id


def test_branch_manager_creates_note_in_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student.id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["author_user_id"] == manager.id


def test_consultancy_owner_creates_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student.id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["author_user_id"] == owner.id


def test_super_admin_creates_note_for_any_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    super_admin = make_db_user(
        db_session, Role.SUPER_ADMIN, tenant_id=None, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_super_admin(super_admin))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student.id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["tenant_id"] == tenant.id


# ---------------------------------------------------------------------------
# POST /notes -- tenant + branch scoping
# ---------------------------------------------------------------------------


def test_post_returns_404_for_cross_tenant_student(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor in tenant A cannot anchor a note to a student in tenant B."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    seed_application(
        db_session,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student_b.id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"


def test_post_returns_404_for_missing_student(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=999999),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_post_returns_404_when_student_id_references_non_student_user(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Probing a staff id must NOT reveal the user's role -- collapse to 404."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    other_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=other_counselor.id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"


def test_counselor_cannot_post_for_student_in_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student_b.id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_branch_manager_cannot_post_for_student_in_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student_b.id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_counselor_cannot_post_for_unassigned_student(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor can only post notes for students they are the assigned counselor on."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    other_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=other_counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student.id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Counselor is not assigned to this student; cannot view notes"
    )


def test_post_returns_422_for_student_mismatch_with_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A different ``student_id`` than the application's student surfaces as 422."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    other_student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(
            student_id=other_student.id, application_id=application.id
        ),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Application is not for the named student"


def test_post_returns_404_for_missing_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student.id, application_id=999999),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


# ---------------------------------------------------------------------------
# POST /notes -- payload validation
# ---------------------------------------------------------------------------


def test_post_rejects_blank_body(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student.id, body=""),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_post_rejects_zero_student_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=0),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_post_rejects_zero_application_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student.id, application_id=0),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_post_rejects_missing_student_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.post(
        "/notes",
        json={"body": "no student id"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /notes -- role permissions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "actor_role",
    [
        Role.STUDENT,
        Role.RECEPTIONIST,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
    ],
)
def test_post_rejects_roles_without_note_create_permission(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    actor_role: Role,
) -> None:
    """Roles without ``NOTE_CREATE`` are rejected (403). Verifier and
    receptionist have NOTE_READ (read-only visibility) but cannot author
    notes per Requirements §5."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    actor = make_db_user(
        db_session, actor_role, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(actor))

    response = client.post(
        "/notes",
        json=_note_payload(student_id=student.id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_post_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post("/notes", json={"student_id": 1, "body": "x"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /notes -- 503 on OperationalError
# ---------------------------------------------------------------------------


def test_post_returns_503_when_commit_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    real_session = db_session

    class _FlakyCommitSession:
        def __init__(self, real):
            self._real = real

        def get(self, *args, **kwargs):
            return self._real.get(*args, **kwargs)

        def commit(self, *args, **kwargs):
            raise OperationalError("stmt", {}, Exception("disk full"))

        def add(self, *args, **kwargs):
            return self._real.add(*args, **kwargs)

        def refresh(self, *args, **kwargs):
            return self._real.refresh(*args, **kwargs)

        def rollback(self, *args, **kwargs):
            return self._real.rollback(*args, **kwargs)

        def execute(self, *args, **kwargs):
            return self._real.execute(*args, **kwargs)

        def scalars(self, *args, **kwargs):
            return self._real.scalars(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    def override_get_db():
        yield _FlakyCommitSession(real_session)

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/notes",
            json=_note_payload(student_id=student.id),
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Notes service is temporarily unavailable"


# ---------------------------------------------------------------------------
# GET /notes -- scoping
# ---------------------------------------------------------------------------


def test_counselor_list_returns_only_notes_for_assigned_students(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    other_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student_mine = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    student_other = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student_mine.id,
        assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student_other.id,
        assigned_counselor_id=other_counselor.id,
    )
    mine = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_mine.id,
        author_user_id=counselor.id,
    )
    not_mine = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_other.id,
        author_user_id=other_counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.get(
        "/notes",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {mine.id}
    assert not_mine.id not in ids


def test_branch_manager_list_returns_branch_scoped_notes(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_a.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    note_a = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_a.id,
        author_user_id=counselor_a.id,
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.get(
        "/notes",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {note_a.id}
    assert note_b.id not in ids


def test_consultancy_owner_list_returns_all_notes_in_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_a.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    note_a = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_a.id,
        author_user_id=counselor_a.id,
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.get(
        "/notes",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {note_a.id, note_b.id}


def test_super_admin_list_returns_all_notes(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    super_admin = make_db_user(
        db_session, Role.SUPER_ADMIN, tenant_id=None, branch_id=None
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    note_a = seed_note(
        db_session,
        tenant_id=tenant_a.id,
        student_id=student_a.id,
        author_user_id=super_admin.id,
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant_b.id,
        student_id=student_b.id,
        author_user_id=super_admin.id,
    )
    override_authenticated_user(_auth_super_admin(super_admin))

    response = client.get(
        "/notes",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {note_a.id, note_b.id}


def test_document_verifier_can_list_notes_tenant_wide(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Document verifier has NOTE_READ per Requirements §5 — they see all
    notes in their tenant (across branches) for context during verification."""
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    verifier = make_db_user(
        db_session, Role.DOCUMENT_VERIFIER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_a.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    note_a = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_a.id,
        author_user_id=counselor_a.id,
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(verifier))

    response = client.get(
        "/notes",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {note_a.id, note_b.id}


def test_receptionist_can_list_notes_tenant_wide(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Receptionist has NOTE_READ for front-desk caller-context visibility."""
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    receptionist = make_db_user(
        db_session, Role.RECEPTIONIST, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_a.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    note_a = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_a.id,
        author_user_id=counselor_a.id,
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(receptionist))

    response = client.get(
        "/notes",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {note_a.id, note_b.id}


def test_student_cannot_list_notes(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student must NEVER be able to list notes — Requirements §5 'hidden from student'."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
    )
    override_authenticated_user(_auth_for(student))

    response = client.get(
        "/notes",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_list_excludes_cross_tenant_notes(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor in tenant A does not see notes from tenant B."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    seed_note(
        db_session,
        tenant_id=tenant_b.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.get(
        "/notes",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_filters_by_student_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student_a = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    note_a = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_a.id,
        author_user_id=counselor.id,
    )
    seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_b.id,
        author_user_id=counselor.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.get(
        f"/notes?student_id={student_a.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {note_a.id}


def test_list_filters_by_application_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    app_one = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    app_two = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    note_one = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
        application_id=app_one.id,
    )
    seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
        application_id=app_two.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.get(
        f"/notes?application_id={app_one.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {note_one.id}


def test_branch_manager_list_rejects_cross_branch_student_id_probe(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Branch manager must NOT probe a student in another branch via the list endpoint."""
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.get(
        f"/notes?student_id={student_b.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_branch_manager_list_rejects_cross_tenant_student_id_probe(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.get(
        f"/notes?student_id={student_b.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_list_rejects_zero_student_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.get(
        "/notes?student_id=0",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_list_rejects_zero_application_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.get(
        "/notes?application_id=0",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_list_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.get("/notes")
    assert response.status_code == 401


def test_list_returns_newest_first(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Notes thread reads top-to-bottom in the UI; the API returns DESC."""
    from datetime import datetime, timedelta, timezone

    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    older = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    newer = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
        created_at=datetime.now(timezone.utc),
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.get(
        "/notes",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["id"] for item in body] == [newer.id, older.id]


# ---------------------------------------------------------------------------
# GET /notes/{id}
# ---------------------------------------------------------------------------


def test_get_note_happy_path(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.get(
        f"/notes/{note.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == note.id


def test_get_note_returns_404_for_missing(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.get(
        "/notes/999999",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_get_note_returns_404_for_cross_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant_b.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.get(
        f"/notes/{note_b.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_get_note_returns_403_for_cross_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.get(
        f"/notes/{note_b.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_get_note_returns_403_for_counselor_not_assigned(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    other_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=other_counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.get(
        f"/notes/{note.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_get_note_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.get("/notes/1")
    assert response.status_code == 401


def test_student_cannot_get_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student must NEVER be able to read notes — Requirements §5 'hidden from student'."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
    )
    override_authenticated_user(_auth_for(student))

    response = client.get(
        f"/notes/{note.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /notes/{id}
# ---------------------------------------------------------------------------


def test_counselor_updates_own_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
        body="Original",
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.patch(
        f"/notes/{note.id}",
        json={"body": "Updated body"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"] == "Updated body"
    assert body["id"] == note.id


def test_branch_manager_updates_own_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=manager.id,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/notes/{note.id}",
        json={"body": "Manager update"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["body"] == "Manager update"


def test_owner_cannot_update_counselor_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Even consultancy owners cannot edit another author's note — author-only enforcement."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.patch(
        f"/notes/{note.id}",
        json={"body": "Sneaky edit"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only the note's author may edit it"


def test_peer_counselor_cannot_update_others_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    other_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=other_counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.patch(
        f"/notes/{note.id}",
        json={"body": "Peer overwrite"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_patch_returns_404_for_missing_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.patch(
        "/notes/999999",
        json={"body": "x"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_patch_returns_404_for_cross_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant_b.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.patch(
        f"/notes/{note_b.id}",
        json={"body": "x"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_branch_manager_cannot_patch_note_in_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.patch(
        f"/notes/{note_b.id}",
        json={"body": "x"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "actor_role",
    [
        Role.STUDENT,
        Role.RECEPTIONIST,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
    ],
)
def test_patch_rejects_roles_without_note_update_permission(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    actor_role: Role,
) -> None:
    """Roles without ``NOTE_UPDATE`` are rejected (403). Verifier and
    receptionist can read notes but cannot edit them."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    actor = make_db_user(
        db_session, actor_role, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=actor.id if actor_role != Role.STUDENT else actor.id,
    )
    override_authenticated_user(_auth_for(actor))

    response = client.patch(
        f"/notes/{note.id}",
        json={"body": "x"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_patch_rejects_blank_body(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.patch(
        f"/notes/{note.id}",
        json={"body": ""},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_patch_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.patch("/notes/1", json={"body": "x"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /notes/{id}
# ---------------------------------------------------------------------------


def test_counselor_deletes_own_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
    )
    note_id = note.id
    override_authenticated_user(_auth_for(counselor))

    response = client.delete(
        f"/notes/{note.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 204
    # Confirm the note is gone.
    from app.models.note import Note

    assert db_session.query(Note).filter(Note.id == note_id).one_or_none() is None


def test_owner_cannot_delete_counselor_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Even consultancy owners cannot delete another author's note."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.delete(
        f"/notes/{note.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only the note's author may delete it"


def test_branch_manager_cannot_delete_note_in_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch_b.id
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.delete(
        f"/notes/{note_b.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "actor_role",
    [
        Role.STUDENT,
        Role.RECEPTIONIST,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
    ],
)
def test_delete_rejects_roles_without_note_delete_permission(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    actor_role: Role,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    actor = make_db_user(
        db_session, actor_role, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=actor.id,
    )
    override_authenticated_user(_auth_for(actor))

    response = client.delete(
        f"/notes/{note.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_delete_returns_404_for_missing_note(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(counselor))

    response = client.delete(
        "/notes/999999",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_delete_returns_404_for_cross_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    counselor_a = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    note_b = seed_note(
        db_session,
        tenant_id=tenant_b.id,
        student_id=student_b.id,
        author_user_id=counselor_b.id,
    )
    override_authenticated_user(_auth_for(counselor_a))

    response = client.delete(
        f"/notes/{note_b.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_delete_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.delete("/notes/1")
    assert response.status_code == 401


def test_delete_returns_503_when_commit_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    real_session = db_session

    class _FlakyCommitSession:
        def __init__(self, real):
            self._real = real

        def get(self, *args, **kwargs):
            return self._real.get(*args, **kwargs)

        def commit(self, *args, **kwargs):
            raise OperationalError("stmt", {}, Exception("disk full"))

        def add(self, *args, **kwargs):
            return self._real.add(*args, **kwargs)

        def refresh(self, *args, **kwargs):
            return self._real.refresh(*args, **kwargs)

        def rollback(self, *args, **kwargs):
            return self._real.rollback(*args, **kwargs)

        def execute(self, *args, **kwargs):
            return self._real.execute(*args, **kwargs)

        def delete(self, *args, **kwargs):
            return self._real.delete(*args, **kwargs)

        def scalars(self, *args, **kwargs):
            return self._real.scalars(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    def override_get_db():
        yield _FlakyCommitSession(real_session)

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.delete(
            f"/notes/{note.id}",
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Notes service is temporarily unavailable"


# ---------------------------------------------------------------------------
# 503 on OperationalError during read paths (GET list / GET single)
# ---------------------------------------------------------------------------


def test_get_note_returns_503_when_db_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    note = seed_note(
        db_session,
        tenant_id=tenant.id,
        student_id=student.id,
        author_user_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    real_session = db_session

    class _FlakyGetSession:
        def __init__(self, real):
            self._real = real

        def get(self, *args, **kwargs):
            raise OperationalError("stmt", {}, Exception("disk full"))

        def commit(self, *args, **kwargs):
            return self._real.commit(*args, **kwargs)

        def add(self, *args, **kwargs):
            return self._real.add(*args, **kwargs)

        def refresh(self, *args, **kwargs):
            return self._real.refresh(*args, **kwargs)

        def rollback(self, *args, **kwargs):
            return self._real.rollback(*args, **kwargs)

        def execute(self, *args, **kwargs):
            return self._real.execute(*args, **kwargs)

        def scalars(self, *args, **kwargs):
            return self._real.scalars(*args, **kwargs)

        def delete(self, *args, **kwargs):
            return self._real.delete(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    def override_get_db():
        yield _FlakyGetSession(real_session)

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get(
            f"/notes/{note.id}",
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Notes service is temporarily unavailable"
