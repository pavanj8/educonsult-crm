"""Tests for the E35 visa outcome update API (Journey J28; issue #195).

Covers the happy path (create + update), tenant scoping, role gating,
in-stage guard (only ``visa_processing`` applications accept an outcome
update), terminal-state rejection, body validation (status required on
create, empty body, max-length status), and the 503 database-unavailable
error path. Mirrors the conventions used in
``tests/visa/test_queue.py`` so the two surfaces read consistently.
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.visa_outcome import VisaOutcome
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
        tenant = Tenant(name="Visa Outcome Tenant", slug=f"visa-outcome-{db_session.info.get('counter', 0)}")
        # Ensure unique slug across tests even within a session.
        suffix = 1
        while db_session.query(Tenant).filter(Tenant.slug == tenant.slug).first() is not None:
            tenant = Tenant(name=tenant.name, slug=f"visa-outcome-{db_session.info.get('counter', 0)}-{suffix}")
            suffix += 1
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


def test_visa_outcome_create_for_visa_stage_application(
    client, db_session, override_authenticated_user
):
    """VISA_PROCESSOR can create the outcome for an application at visa_processing."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={
            "status": "approved",
            "outcome_date": "2026-09-30T10:00:00+00:00",
            "notes": "Stamped at US embassy",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["application_id"] == application.id
    assert body["tenant_id"] == tenant_id
    assert body["status"] == "approved"
    assert body["outcome_date"] is not None
    assert body["notes"] == "Stamped at US embassy"

    stored = db_session.query(VisaOutcome).filter_by(application_id=application.id).one()
    assert stored.status == "approved"
    assert stored.outcome_date is not None
    assert stored.notes == "Stamped at US embassy"


def test_visa_outcome_update_overwrites_existing_row(
    client, db_session, override_authenticated_user
):
    """A second PATCH updates the existing outcome row in place (unique constraint 1:1)."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    first = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "pending", "notes": "Awaiting embassy"},
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]

    second = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={
            "status": "rejected",
            "outcome_date": "2026-09-30T11:00:00+00:00",
            "notes": "Missing financial docs",
        },
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["id"] == first_id, "outcome row id must remain stable across updates"
    assert body["status"] == "rejected"
    assert body["outcome_date"] is not None
    assert body["notes"] == "Missing financial docs"

    # Still exactly one outcome row for this application.
    rows = db_session.query(VisaOutcome).filter_by(application_id=application.id).all()
    assert len(rows) == 1


def test_visa_outcome_partial_update_preserves_other_fields(
    client, db_session, override_authenticated_user
):
    """A PATCH with only one field set leaves the other fields untouched."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    seeded = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={
            "status": "approved",
            "outcome_date": "2026-09-30T10:00:00+00:00",
            "notes": "Original notes",
        },
    )
    assert seeded.status_code == 200

    only_notes = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"notes": "Updated notes"},
    )
    assert only_notes.status_code == 200, only_notes.text
    body = only_notes.json()
    assert body["notes"] == "Updated notes"
    assert body["status"] == "approved"
    assert body["outcome_date"] is not None


@pytest.mark.parametrize(
    "role",
    [Role.STUDENT, Role.COUNSELOR, Role.RECEPTIONIST, Role.BRANCH_MANAGER, Role.DOCUMENT_VERIFIER],
)
def test_visa_outcome_rejects_non_visa_processor_roles(
    client, db_session, override_authenticated_user, role
):
    """Roles without VISA_MANAGE get 403.

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

    response = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_visa_outcome_rejects_visa_processor_without_tenant_scope(
    client, db_session, override_authenticated_user
):
    """A visa processor with no tenant scope gets a 403, not an unscoped update."""
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=999,
        tenant_id=None,
        branch_id=None,
    )

    response = client.patch(
        "/visa/applications/1/outcome",
        json={"status": "approved"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User has no tenant scope"


def test_visa_outcome_rejects_cross_tenant_application(
    client, db_session, override_authenticated_user
):
    """A visa processor in tenant A cannot update an application in tenant B (404)."""
    own_tenant_id, _, own_application = _setup_visa_application(db_session)
    other_tenant = Tenant(name="Other Outcome Tenant", slug="other-outcome-tenant")
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

    response = client.patch(
        f"/visa/applications/{other_application.id}/outcome",
        json={"status": "approved"},
    )

    # Cross-tenant access surfaces as 404 to prevent tenant-id enumeration,
    # matching the E25 / E33 conventions.
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_visa_outcome_returns_404_for_missing_application(
    client, db_session, override_authenticated_user
):
    """A 404 (not a 5xx or a different status) is returned for a non-existent id."""
    tenant_id, _, _ = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        "/visa/applications/99999999/outcome",
        json={"status": "approved"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_visa_outcome_rejects_application_not_at_visa_stage(
    client, db_session, override_authenticated_user
):
    """Applications in stages other than visa_processing cannot have their outcome set."""
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

    response = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved"},
    )

    assert response.status_code == 422
    assert "visa_processing" in response.json()["detail"]


def test_visa_outcome_rejects_terminal_state_application(
    client, db_session, override_authenticated_user
):
    """Terminal applications (enrolled/rejected/withdrawn) cannot be re-outcomed."""
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

    response = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved"},
    )

    assert response.status_code == 422


def test_visa_outcome_rejects_empty_body(client, db_session, override_authenticated_user):
    """An empty PATCH body is rejected as 422 (a no-op outcome is never persisted)."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={},
    )

    assert response.status_code == 422


def test_visa_outcome_create_requires_status(
    client, db_session, override_authenticated_user
):
    """When no outcome row exists, status is required (422 otherwise)."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"notes": "Some context only"},
    )

    assert response.status_code == 422
    assert "status is required" in response.json()["detail"]


def test_visa_outcome_update_without_status_only_updates_notes(
    client, db_session, override_authenticated_user
):
    """Once a row exists, a PATCH without status succeeds (notes-only update)."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    seeded = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved", "notes": "first"},
    )
    assert seeded.status_code == 200

    notes_only = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"notes": "second"},
    )
    assert notes_only.status_code == 200
    body = notes_only.json()
    assert body["status"] == "approved"
    assert body["notes"] == "second"


def test_visa_outcome_rejects_whitespace_only_status(
    client, db_session, override_authenticated_user
):
    """A whitespace-only status is rejected (422) so callers cannot smuggle empty labels."""
    tenant_id, _, application = _setup_visa_application(db_session)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "   "},
    )

    assert response.status_code == 422


def test_visa_outcome_consultancy_owner_can_update(
    client, db_session, override_authenticated_user
):
    """CONSULTANCY_OWNER holds ``visa:manage`` and can record outcomes for own tenant."""
    tenant_id, _, application = _setup_visa_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"


class _FakeSessionFor503:
    """Minimal fake session raising OperationalError on every query.

    Used to test the 503 database-unavailable error path without
    touching the real session the test fixture installs. The
    endpoint hits ``db.get`` (to load the application) and
    ``db.scalar`` (to look up the existing outcome row) -- both
    raise so the endpoint surfaces 503 to the caller. ``commit``
    also raises to exercise the rollback path.
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


def test_visa_outcome_503_on_database_unavailable(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError raised while writing the outcome results in 503."""
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
        response = client.patch(
            f"/visa/applications/{application.id}/outcome",
            json={"status": "approved"},
        )
        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "Visa outcome update is temporarily unavailable"
    finally:
        client.app.dependency_overrides.pop(get_db, None)
