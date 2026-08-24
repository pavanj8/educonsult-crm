"""Tests for the E34 visa detail API (Journey J27; issue #194).

Covers the happy path for GET (no detail yet → 404, then PUT → GET round
trip), role gating (STUDENT, COUNSELOR, RECEPTIONIST, BRANCH_MANAGER,
DOCUMENT_VERIFIER blocked), tenant scoping (cross-tenant → 404, no
tenant scope → 403), in-stage guard (only ``visa_processing`` accepts a
PUT), terminal-state rejection, body validation (empty ``visa_type``,
oversize ``visa_type``, naive ``interview_date``), and the 503
database-unavailable error path. Mirrors the conventions used in
``tests/visa/test_outcome.py`` so the E34 and E35 surfaces read
consistently.
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.visa_detail import VisaDetail
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


def _override(
    override_authenticated_user, *, role: Role, user_id: int, tenant_id: int | None, branch_id: int | None
):
    override_authenticated_user(
        make_authenticated_user(role, user_id=user_id, tenant_id=tenant_id, branch_id=branch_id)
    )


def _setup_visa_application(
    db_session,
    *,
    stage: PipelineStage = PipelineStage.VISA_PROCESSING,
    tenant_id: int | None = None,
):
    """Create a tenant + branch + visa-stage application for the calling test."""
    if tenant_id is None:
        suffix = 1
        slug = "visa-detail"
        while db_session.query(Tenant).filter(Tenant.slug == slug).first() is not None:
            suffix += 1
            slug = f"visa-detail-{suffix}"
        tenant = Tenant(name="Visa Detail Tenant", slug=slug)
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)
        tenant_id = tenant.id

    branch = seed_branch(db_session, tenant_id=tenant_id)
    application = seed_application(
        db_session,
        tenant_id=tenant_id,
        branch_id=branch.id,
        university_id=11,
        program_id=21,
        stage=stage,
    )
    return tenant_id, branch.id, application


# ---------------------------------------------------------------------------
# GET /visa/applications/{id}/details
# ---------------------------------------------------------------------------


def test_visa_detail_get_returns_404_when_no_detail_recorded(
    client, db_session, override_authenticated_user
):
    """A GET for an application that has no detail yet returns 404.

    The frontend collapses 404 into an empty form (record-new flow),
    so the backend must surface "not found" rather than an empty
    payload -- otherwise the frontend would render an empty form
    even after a successful PUT/GET round-trip on a fresh tenant.
    """
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.get(f"/visa/applications/{application.id}/details")

    assert response.status_code == 404
    assert response.json()["detail"] == "Visa detail not found"


def test_visa_detail_get_returns_persisted_row(
    client, db_session, override_authenticated_user
):
    """A GET for an application with a persisted detail returns the row."""
    tenant_id, _, application = _setup_visa_application(db_session)

    now = datetime_now()
    detail = VisaDetail(
        tenant_id=tenant_id,
        application_id=application.id,
        visa_type="F-1 Student",
        interview_date=now,
    )
    db_session.add(detail)
    db_session.commit()
    db_session.refresh(detail)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.get(f"/visa/applications/{application.id}/details")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == detail.id
    assert body["tenant_id"] == tenant_id
    assert body["application_id"] == application.id
    assert body["visa_type"] == "F-1 Student"
    assert body["interview_date"] is not None


def test_visa_detail_get_unauthenticated_is_rejected(client):
    """Unauthenticated GET returns 401."""
    response = client.get("/visa/applications/1/details")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.parametrize(
    "role",
    [Role.STUDENT, Role.COUNSELOR, Role.RECEPTIONIST, Role.BRANCH_MANAGER, Role.DOCUMENT_VERIFIER],
)
def test_visa_detail_get_rejects_non_visa_processor_roles(
    client, db_session, override_authenticated_user, role
):
    """Roles without VISA_MANAGE get 403 on GET.

    CONSULTANCY_OWNER and SUPER_ADMIN intentionally also hold
    ``VISA_MANAGE`` per :data:`app.rbac.permissions.ROLE_PERMISSIONS`;
    STUDENT / COUNSELOR / RECEPTIONIST / BRANCH_MANAGER /
    DOCUMENT_VERIFIER do not, and are blocked here.
    """
    tenant_id, _, application = _setup_visa_application(db_session)

    user = make_db_user(db_session, role, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=role,
        user_id=user.id,
        tenant_id=tenant_id,
        branch_id=user.branch_id,
    )

    response = client.get(f"/visa/applications/{application.id}/details")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_visa_detail_get_rejects_visa_processor_without_tenant_scope(
    client, override_authenticated_user
):
    """A visa processor with no tenant scope gets a 403, not an unscoped read."""
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=999,
        tenant_id=None,
        branch_id=None,
    )

    response = client.get("/visa/applications/1/details")

    assert response.status_code == 403
    assert response.json()["detail"] == "User has no tenant scope"


def test_visa_detail_get_returns_404_for_missing_application(
    client, db_session, override_authenticated_user
):
    """A 404 (not a 5xx) is returned for a non-existent application id."""
    tenant_id, _, _ = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.get("/visa/applications/99999999/details")

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_visa_detail_get_rejects_cross_tenant_application(
    client, db_session, override_authenticated_user
):
    """A visa processor in tenant A cannot read an application's detail in tenant B (404)."""
    own_tenant_id, _, _ = _setup_visa_application(db_session)
    other_tenant = Tenant(name="Other Detail Tenant", slug="other-detail-tenant")
    db_session.add(other_tenant)
    db_session.commit()
    db_session.refresh(other_tenant)
    other_branch = seed_branch(db_session, tenant_id=other_tenant.id)
    other_application = seed_application(
        db_session,
        tenant_id=other_tenant.id,
        branch_id=other_branch.id,
        university_id=99,
        program_id=99,
        stage=PipelineStage.VISA_PROCESSING,
    )

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=own_tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=own_tenant_id,
        branch_id=None,
    )

    response = client.get(f"/visa/applications/{other_application.id}/details")

    # Cross-tenant access surfaces as 404 to prevent tenant-id enumeration,
    # matching the E25 / E33 / E35 conventions.
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


# ---------------------------------------------------------------------------
# PUT /visa/applications/{id}/details
# ---------------------------------------------------------------------------


def test_visa_detail_put_creates_row_on_first_save(
    client, db_session, override_authenticated_user
):
    """A PUT for an application with no detail yet inserts a new VisaDetail row."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={
            "visa_type": "F-1 Student",
            "interview_date": "2026-06-15T10:00:00+00:00",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == tenant_id
    assert body["application_id"] == application.id
    assert body["visa_type"] == "F-1 Student"
    assert body["interview_date"] is not None

    rows = db_session.query(VisaDetail).filter_by(application_id=application.id).all()
    assert len(rows) == 1
    assert rows[0].visa_type == "F-1 Student"
    assert rows[0].interview_date is not None


def test_visa_detail_put_updates_existing_row_in_place(
    client, db_session, override_authenticated_user
):
    """A second PUT updates the existing row (1:1 unique constraint)."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    first = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]

    second = client.put(
        f"/visa/applications/{application.id}/details",
        json={
            "visa_type": "Tier 4 Student",
            "interview_date": "2026-09-30T11:00:00+00:00",
        },
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["id"] == first_id, "detail row id must remain stable across updates"
    assert body["visa_type"] == "Tier 4 Student"
    assert body["interview_date"] is not None

    rows = db_session.query(VisaDetail).filter_by(application_id=application.id).all()
    assert len(rows) == 1


def test_visa_detail_put_round_trip_persists_visa_type_and_interview_date(
    client, db_session, override_authenticated_user
):
    """PUT then GET returns the same visa_type and interview_date (J27 acceptance)."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    put_response = client.put(
        f"/visa/applications/{application.id}/details",
        json={
            "visa_type": "F-1 Student",
            "interview_date": "2026-06-15T10:00:00+00:00",
        },
    )
    assert put_response.status_code == 200, put_response.text

    get_response = client.get(f"/visa/applications/{application.id}/details")
    assert get_response.status_code == 200, get_response.text
    body = get_response.json()
    assert body["visa_type"] == "F-1 Student"
    assert body["interview_date"] is not None


def test_visa_detail_put_accepts_null_interview_date(
    client, db_session, override_authenticated_user
):
    """A null ``interview_date`` is accepted (J27 records the type ahead of the date)."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )

    assert response.status_code == 200, response.text
    assert response.json()["interview_date"] is None


def test_visa_detail_put_clears_interview_date_on_subsequent_save(
    client, db_session, override_authenticated_user
):
    """A second PUT with ``interview_date=null`` clears a previously-recorded date."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    seeded = client.put(
        f"/visa/applications/{application.id}/details",
        json={
            "visa_type": "F-1 Student",
            "interview_date": "2026-06-15T10:00:00+00:00",
        },
    )
    assert seeded.status_code == 200
    assert seeded.json()["interview_date"] is not None

    cleared = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["interview_date"] is None


def test_visa_detail_put_unauthenticated_is_rejected(
    client, db_session
):
    """Unauthenticated PUT returns 401."""
    tenant_id, _, application = _setup_visa_application(db_session)

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.parametrize(
    "role",
    [Role.STUDENT, Role.COUNSELOR, Role.RECEPTIONIST, Role.BRANCH_MANAGER, Role.DOCUMENT_VERIFIER],
)
def test_visa_detail_put_rejects_non_visa_processor_roles(
    client, db_session, override_authenticated_user, role
):
    """Roles without VISA_MANAGE get 403 on PUT."""
    tenant_id, _, application = _setup_visa_application(db_session)

    user = make_db_user(db_session, role, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=role,
        user_id=user.id,
        tenant_id=tenant_id,
        branch_id=user.branch_id,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_visa_detail_put_rejects_visa_processor_without_tenant_scope(
    client, override_authenticated_user
):
    """A visa processor with no tenant scope gets a 403, not an unscoped write."""
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=999,
        tenant_id=None,
        branch_id=None,
    )

    response = client.put(
        "/visa/applications/1/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User has no tenant scope"


def test_visa_detail_put_rejects_cross_tenant_application(
    client, db_session, override_authenticated_user
):
    """A visa processor in tenant A cannot write an application's detail in tenant B (404)."""
    own_tenant_id, _, _ = _setup_visa_application(db_session)
    other_tenant = Tenant(name="Other Detail Write Tenant", slug="other-detail-write-tenant")
    db_session.add(other_tenant)
    db_session.commit()
    db_session.refresh(other_tenant)
    other_branch = seed_branch(db_session, tenant_id=other_tenant.id)
    other_application = seed_application(
        db_session,
        tenant_id=other_tenant.id,
        branch_id=other_branch.id,
        university_id=99,
        program_id=99,
        stage=PipelineStage.VISA_PROCESSING,
    )

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=own_tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=own_tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{other_application.id}/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_visa_detail_put_rejects_application_not_at_visa_stage(
    client, db_session, override_authenticated_user
):
    """Applications in stages other than visa_processing cannot have their detail recorded."""
    tenant_id, _, application = _setup_visa_application(
        db_session, stage=PipelineStage.OFFER_LETTER,
    )

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )

    assert response.status_code == 422
    assert "visa_processing" in response.json()["detail"]


def test_visa_detail_put_rejects_terminal_state_application(
    client, db_session, override_authenticated_user
):
    """Terminal applications (enrolled/rejected/withdrawn) cannot be re-detailed."""
    tenant_id, _, application = _setup_visa_application(
        db_session, stage=PipelineStage.ENROLLED,
    )

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )

    assert response.status_code == 422


def test_visa_detail_put_rejects_empty_visa_type(
    client, db_session, override_authenticated_user
):
    """An empty ``visa_type`` is rejected (422) -- visa_type is the required input."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "", "interview_date": None},
    )

    assert response.status_code == 422


def test_visa_detail_put_rejects_whitespace_only_visa_type(
    client, db_session, override_authenticated_user
):
    """A whitespace-only ``visa_type`` is rejected (422) so callers cannot smuggle empty labels."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "   ", "interview_date": None},
    )

    assert response.status_code == 422


def test_visa_detail_put_rejects_oversize_visa_type(
    client, db_session, override_authenticated_user
):
    """A ``visa_type`` over 100 chars is rejected (422) -- matches the column ceiling."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "x" * 101, "interview_date": None},
    )

    assert response.status_code == 422


def test_visa_detail_put_rejects_naive_interview_date(
    client, db_session, override_authenticated_user
):
    """A naive ``interview_date`` (no tz info) is rejected -- the column is timezone-aware."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={
            "visa_type": "F-1 Student",
            "interview_date": "2026-06-15T10:00:00",  # naive -- no offset
        },
    )

    assert response.status_code == 422


def test_visa_detail_put_consultancy_owner_can_record(
    client, db_session, override_authenticated_user
):
    """CONSULTANCY_OWNER holds ``visa:manage`` and can record details for own tenant."""
    tenant_id, _, application = _setup_visa_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.put(
        f"/visa/applications/{application.id}/details",
        json={"visa_type": "F-1 Student", "interview_date": None},
    )

    assert response.status_code == 200, response.text
    assert response.json()["visa_type"] == "F-1 Student"


# ---------------------------------------------------------------------------
# Helpers + 503 path
# ---------------------------------------------------------------------------


def datetime_now():
    """Local helper: return a tz-aware datetime in UTC for VisaDetail rows."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


class _FakeSessionFor503:
    """Minimal fake session raising OperationalError on every query.

    Used to test the 503 database-unavailable error path without
    touching the real session the test fixture installs. The GET
    endpoint hits ``db.get`` and ``db.scalar``; the PUT endpoint
    hits ``db.scalar`` and ``db.commit`` -- both raise so the
    endpoint surfaces 503 to the caller. ``rollback`` is a no-op
    so we can observe the rollback code path without an actual
    session.
    """

    def get(self, *args: object, **kwargs: object) -> object:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def scalar(self, *args: object, **kwargs: object) -> object:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def scalars(self, *args: object, **kwargs: object) -> object:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def commit(self) -> None:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_visa_detail_get_503_on_database_unavailable(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError raised by the GET query results in 503."""
    from app.db.database import get_db

    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    fake_session = _FakeSessionFor503()

    def _override_get_db():
        yield fake_session

    client.app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.get(f"/visa/applications/{application.id}/details")
        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "Visa detail is temporarily unavailable"
    finally:
        client.app.dependency_overrides.pop(get_db, None)


def test_visa_detail_put_503_on_database_unavailable(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError raised while writing the detail results in 503."""
    from app.db.database import get_db

    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    fake_session = _FakeSessionFor503()

    def _override_get_db():
        yield fake_session

    client.app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.put(
            f"/visa/applications/{application.id}/details",
            json={"visa_type": "F-1 Student", "interview_date": None},
        )
        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "Visa detail is temporarily unavailable"
    finally:
        client.app.dependency_overrides.pop(get_db, None)