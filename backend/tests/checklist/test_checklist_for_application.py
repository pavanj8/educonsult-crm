"""Tests for the E26 checklist-for-application retrieval API (Journey J19).

Covers the ``GET /applications/{application_id}/checklist`` endpoint
that merges per-stage/program :class:`ChecklistItemTemplate` rows with
the latest :class:`StudentDocument` upload for each template.

The endpoint is read-only and surfaces:

* the template metadata (``stage``, ``name``, ``description``,
  ``required``, ``order_index``), and
* the latest upload against the template (or ``None`` if the student
  has not uploaded anything yet).

Authorization matrix under test:

* STUDENT — only own application.
* COUNSELOR — only assigned applications in own branch.
* CONSULTANCY_OWNER / BRANCH_MANAGER — across own tenant (branch
  managers see own branch only).
* SUPER_ADMIN — across all tenants (no tenant filter).
* DOCUMENT_VERIFIER — own tenant.
* RECEPTIONIST / VISA_PROCESSOR — 403.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.models.application import Application
from app.models.student_document import StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.checklist.helpers import seed_checklist_template, seed_student_document
from tests.factories.users import make_authenticated_user, make_db_user
from tests.master_data.helpers import seed_master_data_chain


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _seed_application_with_program(
    db_session,
    *,
    tenant_id: int,
    branch_id: int,
    student_id: int,
    assigned_counselor_id: int | None = None,
    program_id: int,
    university_id: int,
    stage: PipelineStage = PipelineStage.DOCUMENT_VERIFICATION,
) -> Application:
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_id=student_id,
        assigned_counselor_id=assigned_counselor_id,
        university_id=university_id,
        program_id=program_id,
        stage=stage,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_checklist_returns_empty_when_no_templates_exist(
    client, db_session, override_authenticated_user
):
    """No templates seeded → response is the application id + empty items list."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="empty@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"application_id": application.id, "items": []}


def test_checklist_merges_template_and_pending_upload_status(
    client, db_session, override_authenticated_user
):
    """A pending upload is surfaced as upload.status='pending' under the template row."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="student-merge@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    template = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
        description="Color scan of the photo page",
        required=True,
        order_index=1,
    )
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.PENDING,
        uploaded_by_user_id=student.id,
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["application_id"] == application.id
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["template_id"] == template.id
    assert item["stage"] == PipelineStage.DOCUMENT_VERIFICATION.value
    assert item["name"] == "Passport copy"
    assert item["description"] == "Color scan of the photo page"
    assert item["required"] is True
    assert item["order_index"] == 1
    assert item["upload"] is not None
    assert item["upload"]["status"] == StudentDocumentStatus.PENDING.value
    assert item["upload"]["original_filename"] == "passport.pdf"
    assert item["upload"]["verified_at"] is None
    assert item["upload"]["rejection_reason"] is None


def test_checklist_surfaces_approved_upload_status(
    client, db_session, override_authenticated_user
):
    """An approved upload surfaces status='approved' with verified_at populated."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="approved@example.test",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="verifier@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    template = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
    )
    verified_at = datetime.now(timezone.utc) - timedelta(hours=1)
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.APPROVED,
        uploaded_by_user_id=student.id,
        verified_by_user_id=verifier.id,
        verified_at=verified_at,
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["upload"]["status"] == StudentDocumentStatus.APPROVED.value
    assert item["upload"]["verified_at"] is not None
    assert item["upload"]["rejection_reason"] is None


def test_checklist_surfaces_rejected_upload_with_reason(
    client, db_session, override_authenticated_user
):
    """A rejected upload surfaces status='rejected' and the verifier's reason."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="rejected@example.test",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="verifier-rej@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    template = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
    )
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.REJECTED,
        uploaded_by_user_id=student.id,
        verified_by_user_id=verifier.id,
        verified_at=datetime.now(timezone.utc),
        rejection_reason="Image too blurry",
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["upload"]["status"] == StudentDocumentStatus.REJECTED.value
    assert item["upload"]["rejection_reason"] == "Image too blurry"


def test_checklist_template_with_no_upload_has_null_upload_field(
    client, db_session, override_authenticated_user
):
    """A template with no upload yet returns ``upload: None`` (not omitted, not 404)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="not-uploaded@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["upload"] is None


def test_checklist_returns_latest_upload_when_multiple_exist(
    client, db_session, override_authenticated_user
):
    """When a student has uploaded several versions against the same template,
    the endpoint returns the most recent upload (E31 re-upload flow).
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="reupload@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    template = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
    )

    earlier = datetime.now(timezone.utc) - timedelta(hours=2)
    later = datetime.now(timezone.utc) - timedelta(hours=1)

    # First upload, rejected.
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.REJECTED,
        uploaded_by_user_id=student.id,
        uploaded_at=earlier,
        original_filename="passport-v1.pdf",
        rejection_reason="Image too blurry",
    )
    # Second upload, approved (the re-upload).
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.APPROVED,
        uploaded_by_user_id=student.id,
        uploaded_at=later,
        original_filename="passport-v2.pdf",
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    # The endpoint collapses to one row per template and surfaces the latest.
    assert items[0]["upload"]["status"] == StudentDocumentStatus.APPROVED.value
    assert items[0]["upload"]["original_filename"] == "passport-v2.pdf"
    assert items[0]["upload"]["rejection_reason"] is None


def test_checklist_includes_global_and_program_specific_templates(
    client, db_session, override_authenticated_user
):
    """Templates with program_id=NULL apply to every program; program-specific
    templates apply only to their own program. The endpoint includes both
    when the application's program matches the program-specific row.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="global@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )

    # Global template (program_id=None)
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
        order_index=1,
    )
    # Program-specific template (matches application.program_id)
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=chain[2].id,
        name="Program-specific form",
        order_index=2,
    )
    # Other-program-specific template (must NOT appear)
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=chain[2].id + 9999,
        name="Wrong-program form",
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    names = {item["name"] for item in items}
    assert names == {"Passport copy", "Program-specific form"}


def test_checklist_excludes_templates_for_other_stages(
    client, db_session, override_authenticated_user
):
    """Templates are filtered by the application's current stage."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="stage@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )
    # Stage that matches the application
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=None,
        name="Document verification: passport",
    )
    # Different stage — must NOT appear
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=PipelineStage.OFFER_LETTER,
        program_id=None,
        name="Offer letter checklist",
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    names = {item["name"] for item in items}
    assert names == {"Document verification: passport"}


def test_checklist_ordered_by_order_index_then_template_id(
    client, db_session, override_authenticated_user
):
    """Templates with order_index come first (sorted ascending), NULL order_index last."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="order@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )

    # Insertion order: order_index NULL, then 2, then 1 (out of order).
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Last (no order)",
        order_index=None,
    )
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Second",
        order_index=2,
    )
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="First",
        order_index=1,
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    names = [item["name"] for item in items]
    assert names == ["First", "Second", "Last (no order)"]


# ---------------------------------------------------------------------------
# Tenant / branch isolation
# ---------------------------------------------------------------------------


def test_checklist_excludes_templates_from_other_tenants(
    client, db_session, override_authenticated_user
):
    """Templates from another tenant are not visible (multi-tenancy)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    chain_a = seed_master_data_chain(db_session, tenant_id=tenant_a.id)
    student_a = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        email="tenant-a@example.test",
    )
    application_a = _seed_application_with_program(
        db_session,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        student_id=student_a.id,
        program_id=chain_a[2].id,
        university_id=chain_a[1].id,
    )
    # Templates in tenant B — must not appear in tenant A's response.
    seed_checklist_template(
        db_session,
        tenant_id=tenant_b.id,
        stage=application_a.stage,
        program_id=None,
        name="Tenant B only",
    )
    # A template in tenant A — must appear.
    seed_checklist_template(
        db_session,
        tenant_id=tenant_a.id,
        stage=application_a.stage,
        program_id=None,
        name="Tenant A",
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
        f"/applications/{application_a.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    names = {item["name"] for item in items}
    assert names == {"Tenant A"}


def test_checklist_excludes_uploads_from_other_applications(
    client, db_session, override_authenticated_user
):
    """Uploads attached to a different application are not surfaced."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student_a = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="student-a@example.test",
    )
    student_b = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="student-b@example.test",
    )
    application_a = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student_a.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    application_b = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student_b.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    template = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application_a.stage,
        program_id=None,
        name="Passport copy",
    )
    # Upload attached to the OTHER application — must not appear.
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application_b.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.APPROVED,
        uploaded_by_user_id=student_b.id,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student_a.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.get(
        f"/applications/{application_a.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    # No upload surfaced for application_a; the other application's upload is filtered.
    assert items[0]["upload"] is None


def test_checklist_returns_404_for_other_tenant_application(
    client, db_session, override_authenticated_user
):
    """A cross-tenant application lookup is a 404, not a 403 (no enumeration)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    chain_b = seed_master_data_chain(db_session, tenant_id=tenant_b.id)
    student_b = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        email="other-tenant@example.test",
    )
    application_b = _seed_application_with_program(
        db_session,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        program_id=chain_b[2].id,
        university_id=chain_b[1].id,
    )

    # Authenticate as a STUDENT in tenant A and probe application_b.
    student_a = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        email="tenant-a-prober@example.test",
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
        f"/applications/{application_b.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_checklist_returns_404_for_nonexistent_application(
    client, db_session, override_authenticated_user
):
    """A 404 is returned for an application id that does not exist at all."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="nonexistent@example.test",
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
        "/applications/999999/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


# ---------------------------------------------------------------------------
# Authentication and authorization
# ---------------------------------------------------------------------------


def test_checklist_requires_authentication(client, db_session):
    """Unauthenticated callers are rejected with 401."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="anon@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )

    response = client.get(f"/applications/{application.id}/checklist")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_checklist_rejects_invalid_access_token(client):
    response = client.get(
        "/applications/1/checklist",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_checklist_student_can_view_own_application(
    client, db_session, override_authenticated_user
):
    """A STUDENT can read the checklist for their own application."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="own-app@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200


def test_checklist_student_cannot_view_other_students_application(
    client, db_session, override_authenticated_user
):
    """A STUDENT must NOT view another student's checklist (403)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    other_student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="other@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=other_student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )

    attacker = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="attacker@example.test",
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=attacker.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot view another student's checklist"


def test_checklist_counselor_can_view_assigned_application_in_own_branch(
    client, db_session, override_authenticated_user
):
    """A COUNSELOR can read the checklist for an assigned application in their branch."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="counselor-target@example.test",
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="counselor@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200


def test_checklist_counselor_cannot_view_unassigned_application(
    client, db_session, override_authenticated_user
):
    """A COUNSELOR must NOT view an application they aren't assigned to."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="unassigned@example.test",
    )
    other_counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="other-counselor@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=other_counselor.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )

    me = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="me-counselor@example.test",
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=me.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Counselor can only view checklists for their assigned applications"
    )


def test_checklist_counselor_cannot_view_other_branch_application(
    client, db_session, override_authenticated_user
):
    """A COUNSELOR cannot read a checklist for an application in a different branch."""
    branch_a = seed_branch(db_session, tenant_id=1, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=1, name="Branch B", city="Delhi")

    counselor_a = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-a@example.test",
        tenant_id=1,
        branch_id=branch_a.id,
    )
    student_b = make_db_user(
        db_session,
        Role.STUDENT,
        email="student-b@example.test",
        tenant_id=1,
        branch_id=branch_b.id,
    )
    # Application in branch B with no assigned counselor (so the counselor in
    # branch A cannot claim it as "assigned").
    application_b = Application(
        tenant_id=1,
        branch_id=branch_b.id,
        student_id=student_b.id,
        assigned_counselor_id=None,
        university_id=10,
        program_id=20,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )
    db_session.add(application_b)
    db_session.commit()
    db_session.refresh(application_b)

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor_a.id,
            tenant_id=1,
            branch_id=branch_a.id,
        )
    )

    response = client.get(
        f"/applications/{application_b.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    # Branch-scope fires before assignment-scope (the counselor in branch A
    # is in a different branch than the application in branch B regardless
    # of assignment). The detail message is the branch-scope one.
    assert (
        response.json()["detail"]
        == "Cannot view checklist for an application outside your branch"
    )


def test_checklist_branch_manager_can_view_own_branch(
    client, db_session, override_authenticated_user
):
    """A BRANCH_MANAGER can read the checklist for applications in their branch."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="bm-target@example.test",
    )
    bm = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="bm@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            user_id=bm.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200


def test_checklist_consultancy_owner_can_view_any_branch(
    client, db_session, override_authenticated_user
):
    """A CONSULTANCY_OWNER can read the checklist for any application in the tenant."""
    tenant = _create_tenant(db_session)
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="Branch B", city="Delhi")
    chain_a = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        email="owner-target@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        student_id=student.id,
        program_id=chain_a[2].id,
        university_id=chain_a[1].id,
    )
    owner = make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        tenant_id=tenant.id,
        email="owner@example.test",
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.CONSULTANCY_OWNER,
            user_id=owner.id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    # branch_a isn't used directly here; we just ensure the response is fine.
    assert branch_a.id != branch_b.id


def test_checklist_document_verifier_can_view(
    client, db_session, override_authenticated_user
):
    """A DOCUMENT_VERIFIER can read the checklist (for verification workflows)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="verifier-target@example.test",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="docverifier@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=verifier.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200


def test_checklist_super_admin_is_blocked_by_rbac():
    """Super Admin has no ``document:read`` permission in v1; this is a
    design decision (document data is operational, not platform-wide).
    This is an indirect assertion against the permission matrix rather
    than a runtime test (no DB seed needed).
    """
    from app.rbac.permissions import Permission, role_has_permission
    from app.rbac.roles import Role

    assert role_has_permission(Role.SUPER_ADMIN, Permission.DOCUMENT_READ) is False


@pytest.mark.parametrize(
    "role",
    [Role.RECEPTIONIST, Role.VISA_PROCESSOR],
)
def test_checklist_rejects_roles_without_document_read(
    client, db_session, override_authenticated_user, role
):
    """Roles that lack ``document:read`` are blocked with 403 at RBAC."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email=f"{role.value}-target@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )

    user = make_db_user(
        db_session,
        role,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email=f"{role.value}@example.test",
    )
    override_authenticated_user(
        make_authenticated_user(
            role,
            user_id=user.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_checklist_rejects_deactivated_student(
    client, db_session, override_authenticated_user
):
    """A deactivated student cannot read their own checklist (403)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="deactivated@example.test",
        is_active=False,
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is deactivated"


def test_checklist_rejects_student_missing_tenant_scope(
    client, db_session, override_authenticated_user
):
    """A student with tenant_id=None cannot read any checklist (403).

    The student's deactivated/tenant check fires after the application
    lookup: we seed an application the student *would* own so the 404
    branch is bypassed and the deactivated-student check fires.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=999,  # The Student row we'll create below.
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=None,
        branch_id=1,
        email="missing-tenant@example.test",
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Student account is missing tenant scope"


def test_checklist_rejects_counselor_without_branch(
    client, db_session, override_authenticated_user
):
    """A counselor with branch_id=None is blocked from any checklist read."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    # Seed a real application so the 404 branch is bypassed; the counselor
    # is branchless so the application-scope branch check fires.
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="no-branch-target@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=None,
        email="counselor-no-branch@example.test",
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    # The branch-scope check fires before the assignment-scope check; both
    # conditions (``branch_id is None`` and ``branch_id mismatch``) collapse
    # to the same message because they have the same security meaning
    # ("the counselor's branch is unassignable / wrong").
    assert (
        response.json()["detail"]
        == "Cannot view checklist for an application outside your branch"
    )


# ---------------------------------------------------------------------------
# Database availability
# ---------------------------------------------------------------------------


class _FakeSessionFor503:
    """Minimal fake session whose ``get`` always raises OperationalError."""

    def get(self, *args, **kwargs):
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def scalars(self, *args, **kwargs):
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def close(self):
        pass


def test_checklist_returns_503_on_database_unavailable(
    client, db_session, override_authenticated_user
):
    """An OperationalError loading the application surfaces as 503."""
    from app.db.database import get_db

    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="db-down@example.test",
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    fake_session = _FakeSessionFor503()

    def _override_get_db():
        yield fake_session

    client.app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.get(
            "/applications/1/checklist",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Checklist service is temporarily unavailable"
    finally:
        client.app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Real-JWT smoke
# ---------------------------------------------------------------------------


def test_checklist_success_with_real_jwt(client, db_session):
    """The endpoint works end-to-end through a JWT (no auth-override)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="jwt-smoke@example.test",
        password="student-password",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
    )

    login_response = client.post(
        "/auth/login",
        json={"email": "jwt-smoke@example.test", "password": "student-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["application_id"] == application.id
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "Passport copy"


# ---------------------------------------------------------------------------
# Defensive: ordering by id when no order_index is set
# ---------------------------------------------------------------------------


def test_checklist_templates_without_order_index_ordered_by_id(
    client, db_session, override_authenticated_user
):
    """When no order_index is set anywhere, items fall back to id order."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="noorder@example.test",
    )
    application = _seed_application_with_program(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        program_id=chain[2].id,
        university_id=chain[1].id,
    )

    # Insert three templates; their ids come from the monotonic id generator.
    first = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="A",
    )
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="B",
    )
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="C",
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
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    ids = [item["template_id"] for item in items]
    assert ids == sorted(ids)
    assert items[0]["name"] == "A"
    # Sanity: we know the first template's id is the lowest.
    assert items[0]["template_id"] == first.id