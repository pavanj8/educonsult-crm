"""Tests for the E33 visa-stage applications queue API (Journey J26; issue #191).

Covers role gating, tenant scoping, stage filtering, pagination, and
the 503 database-unavailable error path. Mirrors the E28 document-
verifier queue test conventions so the two queues feel symmetric to
the frontend.
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
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


def test_visa_queue_returns_only_visa_stage_applications_in_tenant(
    client, db_session, override_authenticated_user
):
    """Visa processor sees only VISA_PROCESSING applications in their tenant."""
    tenant = Tenant(name="Visa Tenant", slug="visa-tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    other = Tenant(name="Other Tenant", slug="other-tenant")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    branch = seed_branch(db_session, tenant_id=tenant.id)
    other_branch = seed_branch(db_session, tenant_id=other.id)

    # Own tenant: visa-stage application (must appear)
    visa_app = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        university_id=11,
        program_id=21,
        stage=PipelineStage.VISA_PROCESSING,
    )
    # Own tenant: not yet at visa stage (must NOT appear)
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        university_id=12,
        program_id=22,
        stage=PipelineStage.OFFER_LETTER,
    )
    # Own tenant: terminal stage (must NOT appear)
    seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        university_id=13,
        program_id=23,
        stage=PipelineStage.ENROLLED,
    )
    # Other tenant: visa-stage (cross-tenant leak; must NOT appear)
    seed_application(
        db_session,
        tenant_id=other.id,
        branch_id=other_branch.id,
        university_id=14,
        program_id=24,
        stage=PipelineStage.VISA_PROCESSING,
    )

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant.id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.get("/visa/applications/queue")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == visa_app.id
    assert item["tenant_id"] == tenant.id
    assert item["stage"] == PipelineStage.VISA_PROCESSING.value
    assert item["student_id"] == visa_app.student_id
    assert item["university_id"] == 11
    assert item["program_id"] == 21


def test_visa_queue_excludes_loan_processing_applications(
    client, db_session, override_authenticated_user
):
    """Loan Processing is a sibling non-terminal stage; only VISA_PROCESSING is returned."""
    tenant = Tenant(name="LP Tenant", slug="lp-tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    loan_app = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        stage=PipelineStage.LOAN_PROCESSING,
    )
    visa_app = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        stage=PipelineStage.VISA_PROCESSING,
    )

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant.id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.get("/visa/applications/queue")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {visa_app.id}
    assert loan_app.id not in ids


def test_visa_queue_is_paginatable(client, db_session, override_authenticated_user):
    """The queue supports limit/offset and orders by application.id ascending."""
    tenant = Tenant(name="Paged Visa Tenant", slug="paged-visa")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    app_ids = [
        seed_application(
            db_session,
            tenant_id=tenant.id,
            branch_id=branch.id,
            university_id=10 + i,
            program_id=20 + i,
            stage=PipelineStage.VISA_PROCESSING,
        ).id
        for i in range(3)
    ]

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant.id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    first_page = client.get("/visa/applications/queue?limit=2&offset=0")
    assert first_page.status_code == 200, first_page.text
    body = first_page.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == sorted(app_ids)[:2]

    second_page = client.get("/visa/applications/queue?limit=2&offset=2")
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert [item["id"] for item in second_body["items"]] == sorted(app_ids)[2:]


def test_visa_queue_empty_for_tenant_with_no_visa_applications(
    client, db_session, override_authenticated_user
):
    """An empty visa stage in a tenant returns an empty queue."""
    tenant = Tenant(name="Empty Tenant", slug="empty-tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant.id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.get("/visa/applications/queue")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_visa_queue_unauthenticated_is_rejected(client):
    """Unauthenticated requests get 401."""
    response = client.get("/visa/applications/queue")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.parametrize(
    "role",
    [Role.STUDENT, Role.COUNSELOR, Role.RECEPTIONIST, Role.BRANCH_MANAGER, Role.DOCUMENT_VERIFIER],
)
def test_visa_queue_rejects_non_visa_processor_roles(
    client, db_session, override_authenticated_user, role
):
    """Roles without VISA_MANAGE get 403.

    CONSULTANCY_OWNER and SUPER_ADMIN intentionally also hold
    ``VISA_MANAGE`` per :data:`app.rbac.permissions.ROLE_PERMISSIONS`
    (consultancy owners are platform-wide within their tenant; super
    admins are platform-wide). STUDENT / COUNSELOR / RECEPTIONIST /
    BRANCH_MANAGER / DOCUMENT_VERIFIER do not hold it and are blocked.
    """
    user = make_db_user(db_session, role, tenant_id=1)
    _override(
        override_authenticated_user,
        role=role,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )

    response = client.get("/visa/applications/queue")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_visa_queue_rejects_visa_processor_without_tenant_scope(
    client, override_authenticated_user
):
    """A visa processor with no tenant scope gets a 403, not an unscoped list."""
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=999,
        tenant_id=None,
        branch_id=None,
    )

    response = client.get("/visa/applications/queue")

    assert response.status_code == 403
    assert response.json()["detail"] == "User has no tenant scope"


def test_visa_queue_does_not_leak_other_tenants_data(
    client, db_session, override_authenticated_user
):
    """Two tenants; only the caller's tenant's visa applications are returned."""
    tenant_one = Tenant(name="One", slug="one")
    tenant_two = Tenant(name="Two", slug="two")
    db_session.add_all([tenant_one, tenant_two])
    db_session.commit()
    db_session.refresh(tenant_one)
    db_session.refresh(tenant_two)

    branch_one = seed_branch(db_session, tenant_id=tenant_one.id)
    branch_two = seed_branch(db_session, tenant_id=tenant_two.id)

    own_app = seed_application(
        db_session,
        tenant_id=tenant_one.id,
        branch_id=branch_one.id,
        stage=PipelineStage.VISA_PROCESSING,
    )
    other_app = seed_application(
        db_session,
        tenant_id=tenant_two.id,
        branch_id=branch_two.id,
        stage=PipelineStage.VISA_PROCESSING,
    )

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=tenant_one.id)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=tenant_one.id,
        branch_id=None,
    )

    response = client.get("/visa/applications/queue")

    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert ids == {own_app.id}
    assert other_app.id not in ids
    assert body["total"] == 1


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=101",
        "limit=abc",
        "offset=-1",
    ],
)
def test_visa_queue_rejects_invalid_pagination(
    client, db_session, override_authenticated_user, query
):
    """Out-of-range or non-integer pagination params get a 422."""
    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=1)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=1,
        branch_id=None,
    )

    response = client.get(f"/visa/applications/queue?{query}")

    assert response.status_code == 422


class _FakeSessionFor503:
    """Minimal fake session whose scalars / scalar always raise OperationalError.

    Used to test the 503 database-unavailable error path without
    touching the real session the test fixture installs.
    """

    def scalar(self, *args: object, **kwargs: object) -> object:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def scalars(self, *args: object, **kwargs: object) -> object:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def close(self) -> None:
        pass


def test_visa_queue_503_on_database_unavailable(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError raised by the query results in 503 with the visa-queue detail."""
    from app.db.database import get_db

    visa_user = make_db_user(db_session, Role.VISA_PROCESSOR, tenant_id=1)
    _override(
        override_authenticated_user,
        role=Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=1,
        branch_id=None,
    )

    fake_session = _FakeSessionFor503()

    def _override_get_db():
        yield fake_session

    client.app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.get("/visa/applications/queue")
        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "Visa queue is temporarily unavailable"
    finally:
        client.app.dependency_overrides.pop(get_db, None)
