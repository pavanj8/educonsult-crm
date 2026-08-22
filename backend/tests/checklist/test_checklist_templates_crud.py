"""Tests for the E15 checklist-template CRUD API (Journey J8).

Exercises the admin endpoints owners/branch managers use to define
the document checklist for a stage/program:

* ``GET    /checklist-templates``
* ``POST   /checklist-templates``
* ``GET    /checklist-templates/{id}``
* ``PATCH  /checklist-templates/{id}``
* ``DELETE /checklist-templates/{id}``

Coverage
--------

* Each endpoint succeeds for an admin role in the caller's tenant.
* ``checklist_template:manage`` permission is required — only
  CONSULTANCY_OWNER and BRANCH_MANAGER are granted; every other role
  is denied with 403 (including SUPER_ADMIN, by design).
* Writes inherit ``tenant_id`` from the authenticated caller.
* Cross-tenant reads surface as 404 (never 403), so tenant ids cannot
  be enumerated by probing.
* The optional ``program_id`` FK must resolve to a program in the
  caller's tenant; cross-tenant FK values yield 422.
* List endpoint filters by ``stage`` and ``program_id`` and sorts
  results deterministically.
* Stage / program association is preserved across create + read +
  update + list paths.

The tests use the ``override_authenticated_user`` fixture from the
shared conftest and the ``seed_*`` helpers in
:mod:`tests.master_data.helpers` / :mod:`tests.branches.helpers`.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.models.checklist_item_template import ChecklistItemTemplate
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user
from tests.master_data.helpers import seed_master_data_chain


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _make_admin_headers(
    db_session,
    override_authenticated_user,
    *,
    role: Role,
    tenant_id: int,
    branch_id: int | None = None,
):
    """Override the authenticated user and return the bearer headers."""
    user_id = make_authenticated_user(
        role,
        tenant_id=tenant_id,
        branch_id=branch_id,
    ).id
    override_authenticated_user(
        make_authenticated_user(
            role,
            user_id=user_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
    )
    return {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_checklist_templates_empty(
    client, db_session, override_authenticated_user
):
    """No templates seeded → empty list (200)."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    response = client.get("/checklist-templates", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_list_checklist_templates_returns_only_callers_tenant(
    client, db_session, override_authenticated_user
):
    """Templates from another tenant are not visible (multi-tenancy)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    headers_a = _make_admin_headers(
        db_session,
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        tenant_id=tenant_a.id,
    )

    # Tenant A template (must appear)
    now = datetime.now(timezone.utc)
    template_a = ChecklistItemTemplate(
        tenant_id=tenant_a.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=None,
        name="Tenant A: Passport copy",
        required=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template_a)
    # Tenant B template (must NOT appear)
    template_b = ChecklistItemTemplate(
        tenant_id=tenant_b.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=None,
        name="Tenant B: Passport copy",
        required=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template_b)
    db_session.commit()

    response = client.get("/checklist-templates", headers=headers_a)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == {"Tenant A: Passport copy"}


def test_list_checklist_templates_filters_by_stage(
    client, db_session, override_authenticated_user
):
    """``?stage=...`` narrows the list to templates targeting that stage."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.DOCUMENT_VERIFICATION,
                program_id=None,
                name="Doc-ver passport",
                required=True,
                created_at=now,
                updated_at=now,
            ),
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.OFFER_LETTER,
                program_id=None,
                name="Offer letter form",
                required=True,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/checklist-templates",
        params={"stage": PipelineStage.DOCUMENT_VERIFICATION.value},
        headers=headers,
    )
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == {"Doc-ver passport"}


def test_list_checklist_templates_filters_by_program_id(
    client, db_session, override_authenticated_user
):
    """``?program_id=...`` narrows the list to program-scoped templates."""
    tenant = _create_tenant(db_session)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.DOCUMENT_VERIFICATION,
                program_id=None,
                name="Global passport",
                required=True,
                created_at=now,
                updated_at=now,
            ),
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.DOCUMENT_VERIFICATION,
                program_id=chain[2].id,
                name="Program-specific form",
                required=True,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/checklist-templates",
        params={"program_id": chain[2].id},
        headers=headers,
    )
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == {"Program-specific form"}


def test_list_checklist_templates_sorted_deterministically(
    client, db_session, override_authenticated_user
):
    """Results are sorted by (stage, order_index NULLS LAST, id)."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            # Insertion out of order: order_index NULL first, then 2, then 1.
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.DOCUMENT_VERIFICATION,
                program_id=None,
                name="DV: no order",
                order_index=None,
                created_at=now,
                updated_at=now,
            ),
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.DOCUMENT_VERIFICATION,
                program_id=None,
                name="DV: order 2",
                order_index=2,
                created_at=now,
                updated_at=now,
            ),
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.DOCUMENT_VERIFICATION,
                program_id=None,
                name="DV: order 1",
                order_index=1,
                created_at=now,
                updated_at=now,
            ),
            # Different stage — comes before the DOCUMENT_VERIFICATION rows
            # alphabetically by enum value (registered < document_verification).
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.REGISTERED,
                program_id=None,
                name="REG: passport",
                order_index=1,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/checklist-templates", headers=headers)

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    # stage is sorted by enum value (alphabetical), so document_verification
    # ('d') < registered ('r'); within each stage, order_index asc NULLS LAST,
    # then id as a stable tie-breaker.
    assert names == [
        "DV: order 1",
        "DV: order 2",
        "DV: no order",
        "REG: passport",
    ]


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_checklist_template_success_as_owner(
    client, db_session, override_authenticated_user
):
    """An owner can create a template; tenant id is inherited from the caller."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    response = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "name": "Passport copy",
            "description": "Color scan of the photo page",
            "required": True,
            "order_index": 1,
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["tenant_id"] == tenant.id
    assert body["stage"] == PipelineStage.DOCUMENT_VERIFICATION.value
    assert body["program_id"] is None
    assert body["name"] == "Passport copy"
    assert body["description"] == "Color scan of the photo page"
    assert body["required"] is True
    assert body["order_index"] == 1


def test_create_checklist_template_success_as_branch_manager(
    client, db_session, override_authenticated_user
):
    """A branch manager can create a template in their tenant."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    headers = _make_admin_headers(
        db_session,
        override_authenticated_user,
        role=Role.BRANCH_MANAGER,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.REGISTERED.value,
            "name": "10th-grade transcripts",
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == tenant.id
    assert body["stage"] == PipelineStage.REGISTERED.value
    assert body["name"] == "10th-grade transcripts"
    assert body["required"] is True  # default
    assert body["program_id"] is None
    assert body["order_index"] is None


def test_create_checklist_template_with_program_association(
    client, db_session, override_authenticated_user
):
    """A template can be narrowed to a specific program via program_id."""
    tenant = _create_tenant(db_session)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    response = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "program_id": chain[2].id,
            "name": "Program-specific form",
            "required": False,
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["program_id"] == chain[2].id
    assert body["required"] is False


def test_create_checklist_template_strips_whitespace(
    client, db_session, override_authenticated_user
):
    """Leading/trailing whitespace in ``name`` and ``description`` is trimmed."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    response = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "name": "  Passport copy  ",
            "description": "  Color scan of the photo page  ",
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Passport copy"
    assert body["description"] == "Color scan of the photo page"


def test_create_checklist_template_rejects_blank_name(
    client, db_session, override_authenticated_user
):
    """Blank / whitespace-only ``name`` is rejected with 422."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    response = client.post(
        "/checklist-templates",
        json={"stage": PipelineStage.DOCUMENT_VERIFICATION.value, "name": "   "},
        headers=headers,
    )

    assert response.status_code == 422


def test_create_checklist_template_rejects_cross_tenant_program(
    client, db_session, override_authenticated_user
):
    """A ``program_id`` that belongs to another tenant yields 422 (not 404)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    chain_b = seed_master_data_chain(db_session, tenant_id=tenant_b.id)
    headers = _make_admin_headers(
        db_session,
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        tenant_id=tenant_a.id,
    )

    response = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "program_id": chain_b[2].id,
            "name": "Stolen program id",
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid program for the caller's tenant"


def test_create_checklist_template_rejects_nonexistent_program(
    client, db_session, override_authenticated_user
):
    """A non-existent ``program_id`` is unprocessable (422)."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    response = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "program_id": 999999,
            "name": "Stale program id",
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid program for the caller's tenant"


# ---------------------------------------------------------------------------
# Read one
# ---------------------------------------------------------------------------


def test_get_checklist_template_success(
    client, db_session, override_authenticated_user
):
    """A template can be read by id."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    create = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "name": "Passport copy",
            "required": True,
        },
        headers=headers,
    )
    template_id = create.json()["id"]

    response = client.get(f"/checklist-templates/{template_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == template_id
    assert body["name"] == "Passport copy"
    assert body["stage"] == PipelineStage.DOCUMENT_VERIFICATION.value


def test_get_checklist_template_returns_404_for_other_tenant(
    client, db_session, override_authenticated_user
):
    """A cross-tenant id lookup is a 404 (never 403) — no enumeration."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    now = datetime.now(timezone.utc)
    template_b = ChecklistItemTemplate(
        tenant_id=tenant_b.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=None,
        name="Tenant B template",
        required=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template_b)
    db_session.commit()
    db_session.refresh(template_b)

    headers = _make_admin_headers(
        db_session,
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        tenant_id=tenant_a.id,
    )

    response = client.get(
        f"/checklist-templates/{template_b.id}", headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Checklist template not found"


def test_get_checklist_template_returns_404_for_nonexistent_id(
    client, db_session, override_authenticated_user
):
    """A non-existent id is a 404."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    response = client.get("/checklist-templates/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Checklist template not found"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_checklist_template_partial(
    client, db_session, override_authenticated_user
):
    """A PATCH with only some fields updates just those fields."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    create = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "name": "Passport copy",
            "description": "Original description",
            "required": True,
        },
        headers=headers,
    )
    template_id = create.json()["id"]

    response = client.patch(
        f"/checklist-templates/{template_id}",
        json={"name": "Updated passport copy"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated passport copy"
    # Other fields preserved
    assert body["description"] == "Original description"
    assert body["required"] is True
    assert body["stage"] == PipelineStage.DOCUMENT_VERIFICATION.value


def test_update_checklist_template_can_change_stage(
    client, db_session, override_authenticated_user
):
    """A template's stage can be reassigned via PATCH (stage/program association)."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    create = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "name": "Passport copy",
        },
        headers=headers,
    )
    template_id = create.json()["id"]

    response = client.patch(
        f"/checklist-templates/{template_id}",
        json={"stage": PipelineStage.OFFER_LETTER.value},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["stage"] == PipelineStage.OFFER_LETTER.value


def test_update_checklist_template_can_change_program_association(
    client, db_session, override_authenticated_user
):
    """A template's program_id can be re-assigned to another program in the tenant."""
    tenant = _create_tenant(db_session)
    country_b, university_b, program_b = seed_master_data_chain(
        db_session, tenant_id=tenant.id
    )
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    create = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "program_id": program_b.id,
            "name": "Program-specific form",
        },
        headers=headers,
    )
    template_id = create.json()["id"]
    assert create.json()["program_id"] == program_b.id

    # Re-assign to NULL (global).
    response = client.patch(
        f"/checklist-templates/{template_id}",
        json={"program_id": None},
        headers=headers,
    )
    assert response.status_code == 200
    # Note: ``None`` is excluded by Pydantic's ``exclude_unset`` when the
    # field is omitted from the payload; setting ``program_id: null``
    # in the JSON body is an *explicit* unset, so it is honored.
    assert response.json()["program_id"] is None


def test_update_checklist_template_rejects_cross_tenant_program(
    client, db_session, override_authenticated_user
):
    """Updating ``program_id`` to a row outside the caller's tenant yields 422."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    chain_b = seed_master_data_chain(db_session, tenant_id=tenant_b.id)
    headers = _make_admin_headers(
        db_session,
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        tenant_id=tenant_a.id,
    )

    create = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "name": "A's template",
        },
        headers=headers,
    )
    template_id = create.json()["id"]

    response = client.patch(
        f"/checklist-templates/{template_id}",
        json={"program_id": chain_b[2].id},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid program for the caller's tenant"


def test_update_checklist_template_rejects_empty_body(
    client, db_session, override_authenticated_user
):
    """An empty PATCH body is rejected with 422."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    create = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "name": "Passport copy",
        },
        headers=headers,
    )
    template_id = create.json()["id"]

    response = client.patch(
        f"/checklist-templates/{template_id}", json={}, headers=headers
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "At least one field must be provided"


def test_update_checklist_template_returns_404_for_other_tenant(
    client, db_session, override_authenticated_user
):
    """Updating a template in another tenant yields 404, never 403."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    now = datetime.now(timezone.utc)
    template_b = ChecklistItemTemplate(
        tenant_id=tenant_b.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=None,
        name="Tenant B template",
        required=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template_b)
    db_session.commit()
    db_session.refresh(template_b)

    headers = _make_admin_headers(
        db_session,
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        tenant_id=tenant_a.id,
    )

    response = client.patch(
        f"/checklist-templates/{template_b.id}",
        json={"name": "Hacked"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Checklist template not found"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_checklist_template_success(
    client, db_session, override_authenticated_user
):
    """Deleting a template returns 204 and removes the row."""
    tenant = _create_tenant(db_session)
    headers = _make_admin_headers(
        db_session, override_authenticated_user, role=Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )

    create = client.post(
        "/checklist-templates",
        json={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "name": "Passport copy",
        },
        headers=headers,
    )
    template_id = create.json()["id"]

    delete = client.delete(
        f"/checklist-templates/{template_id}", headers=headers
    )
    assert delete.status_code == 204
    assert delete.content == b""

    # Subsequent reads should return 404.
    followup = client.get(
        f"/checklist-templates/{template_id}", headers=headers
    )
    assert followup.status_code == 404


def test_delete_checklist_template_returns_404_for_other_tenant(
    client, db_session, override_authenticated_user
):
    """Deleting a template in another tenant yields 404, never 403."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    now = datetime.now(timezone.utc)
    template_b = ChecklistItemTemplate(
        tenant_id=tenant_b.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=None,
        name="Tenant B template",
        required=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template_b)
    db_session.commit()
    db_session.refresh(template_b)

    headers = _make_admin_headers(
        db_session,
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        tenant_id=tenant_a.id,
    )

    response = client.delete(
        f"/checklist-templates/{template_b.id}", headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Checklist template not found"


# ---------------------------------------------------------------------------
# Authentication / authorization
# ---------------------------------------------------------------------------


def test_endpoints_require_authentication(client, db_session):
    """Unauthenticated callers are rejected with 401 on every endpoint."""
    # Create
    response = client.post(
        "/checklist-templates",
        json={"stage": PipelineStage.DOCUMENT_VERIFICATION.value, "name": "x"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

    # List
    response = client.get("/checklist-templates")
    assert response.status_code == 401

    # Read
    response = client.get("/checklist-templates/1")
    assert response.status_code == 401

    # Update
    response = client.patch("/checklist-templates/1", json={"name": "x"})
    assert response.status_code == 401

    # Delete
    response = client.delete("/checklist-templates/1")
    assert response.status_code == 401


def test_endpoints_reject_invalid_access_token(client):
    response = client.get(
        "/checklist-templates",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


@pytest.mark.parametrize(
    "role",
    [
        Role.STUDENT,
        Role.COUNSELOR,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
        Role.SUPER_ADMIN,
    ],
)
def test_create_rejects_roles_without_checklist_template_manage(
    client, db_session, override_authenticated_user, role
):
    """Roles that lack ``checklist_template:manage`` are blocked at RBAC."""
    # Pick any non-Super-Admin role's auto tenant_id=1 for the permission check.
    user_id = make_authenticated_user(role).id
    override_authenticated_user(
        make_authenticated_user(role, user_id=user_id, tenant_id=1, branch_id=None)
    )

    response = client.post(
        "/checklist-templates",
        json={"stage": PipelineStage.DOCUMENT_VERIFICATION.value, "name": "x"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.parametrize(
    "role",
    [
        Role.STUDENT,
        Role.COUNSELOR,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
        Role.SUPER_ADMIN,
    ],
)
def test_list_rejects_roles_without_checklist_template_manage(
    client, db_session, override_authenticated_user, role
):
    """The same RBAC rule applies to the list endpoint."""
    user_id = make_authenticated_user(role).id
    override_authenticated_user(
        make_authenticated_user(role, user_id=user_id, tenant_id=1, branch_id=None)
    )

    response = client.get(
        "/checklist-templates",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


# ---------------------------------------------------------------------------
# Database availability
# ---------------------------------------------------------------------------


class _FakeSessionFor503:
    """Minimal fake session whose ``get``/``scalars`` always raise OperationalError."""

    def get(self, *args, **kwargs):
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def scalars(self, *args, **kwargs):
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def close(self):
        pass


def test_list_returns_503_on_database_unavailable(
    client, db_session, override_authenticated_user
):
    """An OperationalError during the list query surfaces as 503."""
    from app.db.database import get_db

    tenant = _create_tenant(db_session)
    user_id = make_authenticated_user(
        Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    ).id
    override_authenticated_user(
        make_authenticated_user(
            Role.CONSULTANCY_OWNER,
            user_id=user_id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    fake_session = _FakeSessionFor503()

    def _override_get_db():
        yield fake_session

    client.app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.get(
            "/checklist-templates",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 503
        assert (
            response.json()["detail"]
            == "Checklist template service is temporarily unavailable"
        )
    finally:
        client.app.dependency_overrides.pop(get_db, None)