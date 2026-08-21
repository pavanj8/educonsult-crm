"""Tests for the StudentDocument ORM model (E26 read-model side; E27 schema).

Exercises column shape, persistence, the default ``pending`` status,
nullable ``checklist_item_template_id`` (NULL = ad-hoc upload),
nullable verifier fields, and rejection-reason semantics.
"""

from datetime import datetime, timezone

from sqlalchemy import inspect, select

from app.models.application import Application
from app.models.checklist_item_template import ChecklistItemTemplate
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.pipeline.stages import PipelineStage


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_application(db_session, *, tenant_id: int = 1, student_id: int = 100) -> Application:
    now = _utc_now()
    application = Application(
        tenant_id=tenant_id,
        student_id=student_id,
        university_id=10,
        program_id=20,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application


def _seed_template(db_session, *, tenant_id: int = 1) -> ChecklistItemTemplate:
    now = _utc_now()
    template = ChecklistItemTemplate(
        tenant_id=tenant_id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=None,
        name="Passport copy",
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


def test_student_document_model_has_required_columns():
    column_names = {column.key for column in inspect(StudentDocument).columns}
    assert column_names == {
        "id",
        "tenant_id",
        "application_id",
        "checklist_item_template_id",
        "status",
        "original_filename",
        "content_type",
        "size_bytes",
        "storage_path",
        "uploaded_by_user_id",
        "uploaded_at",
        "verified_by_user_id",
        "verified_at",
        "rejection_reason",
        "created_at",
        "updated_at",
    }


def test_student_document_persists_full_pending_row(db_session):
    """A pending StudentDocument row with every required field round-trips."""
    now = _utc_now()
    application = _seed_application(db_session)
    template = _seed_template(db_session)

    document = StudentDocument(
        tenant_id=1,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.PENDING,
        original_filename="passport.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        storage_path="tenants/1/applications/100/passport.pdf",
        uploaded_by_user_id=100,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    assert document.id is not None
    assert document.tenant_id == 1
    assert document.application_id == application.id
    assert document.checklist_item_template_id == template.id
    assert document.status == StudentDocumentStatus.PENDING
    assert document.original_filename == "passport.pdf"
    assert document.content_type == "application/pdf"
    assert document.size_bytes == 1024
    assert (
        document.storage_path
        == "tenants/1/applications/100/passport.pdf"
    )
    assert document.uploaded_by_user_id == 100
    # SQLite drops tzinfo on round-trip; compare the absolute UTC instant.
    assert document.uploaded_at.replace(tzinfo=timezone.utc) == now
    assert document.verified_by_user_id is None
    assert document.verified_at is None
    assert document.rejection_reason is None


def test_student_document_status_defaults_to_pending(db_session):
    """A new row defaults to ``pending`` before a verifier acts on it."""
    now = _utc_now()
    application = _seed_application(db_session)
    template = _seed_template(db_session)

    document = StudentDocument(
        tenant_id=1,
        application_id=application.id,
        checklist_item_template_id=template.id,
        original_filename="passport.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        storage_path="tenants/1/applications/100/passport.pdf",
        uploaded_by_user_id=100,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    assert document.status == StudentDocumentStatus.PENDING


def test_student_document_can_be_approved(db_session):
    """A verifier can mark a document ``approved`` (Journey J22)."""
    now = _utc_now()
    application = _seed_application(db_session)
    template = _seed_template(db_session)

    document = StudentDocument(
        tenant_id=1,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.APPROVED,
        original_filename="passport.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        storage_path="tenants/1/applications/100/passport.pdf",
        uploaded_by_user_id=100,
        uploaded_at=now,
        verified_by_user_id=200,
        verified_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    assert document.status == StudentDocumentStatus.APPROVED
    assert document.verified_by_user_id == 200
    assert document.verified_at is not None


def test_student_document_can_be_rejected_with_reason(db_session):
    """A verifier can mark a document ``rejected`` with a free-text reason (Journey J23)."""
    now = _utc_now()
    application = _seed_application(db_session)
    template = _seed_template(db_session)

    document = StudentDocument(
        tenant_id=1,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.REJECTED,
        original_filename="passport.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        storage_path="tenants/1/applications/100/passport.pdf",
        uploaded_by_user_id=100,
        uploaded_at=now,
        verified_by_user_id=200,
        verified_at=now,
        rejection_reason="Image is too blurry to read",
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    assert document.status == StudentDocumentStatus.REJECTED
    assert document.rejection_reason == "Image is too blurry to read"
    assert document.verified_by_user_id == 200


def test_student_document_checklist_item_template_id_is_nullable(db_session):
    """``checklist_item_template_id`` is nullable for ad-hoc uploads."""
    now = _utc_now()
    application = _seed_application(db_session)

    document = StudentDocument(
        tenant_id=1,
        application_id=application.id,
        checklist_item_template_id=None,
        status=StudentDocumentStatus.PENDING,
        original_filename="extra.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        storage_path="tenants/1/applications/100/extra.pdf",
        uploaded_by_user_id=100,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    assert document.checklist_item_template_id is None


def test_student_document_verifier_fields_are_nullable_for_pending(db_session):
    """``verified_by_user_id`` / ``verified_at`` / ``rejection_reason`` are NULL while pending."""
    now = _utc_now()
    application = _seed_application(db_session)
    template = _seed_template(db_session)

    document = StudentDocument(
        tenant_id=1,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.PENDING,
        original_filename="passport.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        storage_path="tenants/1/applications/100/passport.pdf",
        uploaded_by_user_id=100,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    assert document.verified_by_user_id is None
    assert document.verified_at is None
    assert document.rejection_reason is None


def test_student_document_persists_status_value(db_session):
    """The status column stores the snake_case enum value (e.g. 'approved')."""
    now = _utc_now()
    application = _seed_application(db_session)
    template = _seed_template(db_session)

    document = StudentDocument(
        tenant_id=1,
        application_id=application.id,
        checklist_item_template_id=template.id,
        status=StudentDocumentStatus.APPROVED,
        original_filename="passport.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        storage_path="tenants/1/applications/100/passport.pdf",
        uploaded_by_user_id=100,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()

    stored_status = db_session.execute(
        select(StudentDocument.__table__.c.status).where(
            StudentDocument.__table__.c.original_filename == "passport.pdf"
        )
    ).scalar_one()
    assert stored_status == StudentDocumentStatus.APPROVED.value


def test_student_document_tenant_scoping(db_session):
    """Two tenants' uploads coexist and are addressable by id."""
    now = _utc_now()
    app_t1 = Application(
        tenant_id=1,
        student_id=100,
        university_id=10,
        program_id=20,
        created_at=now,
        updated_at=now,
    )
    app_t2 = Application(
        tenant_id=2,
        student_id=200,
        university_id=10,
        program_id=20,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([app_t1, app_t2])
    db_session.commit()
    db_session.refresh(app_t1)
    db_session.refresh(app_t2)

    doc_t1 = StudentDocument(
        tenant_id=1,
        application_id=app_t1.id,
        checklist_item_template_id=None,
        status=StudentDocumentStatus.PENDING,
        original_filename="t1.pdf",
        content_type="application/pdf",
        size_bytes=1,
        storage_path="tenants/1/x.pdf",
        uploaded_by_user_id=100,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    doc_t2 = StudentDocument(
        tenant_id=2,
        application_id=app_t2.id,
        checklist_item_template_id=None,
        status=StudentDocumentStatus.PENDING,
        original_filename="t2.pdf",
        content_type="application/pdf",
        size_bytes=1,
        storage_path="tenants/2/x.pdf",
        uploaded_by_user_id=200,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([doc_t1, doc_t2])
    db_session.commit()

    assert doc_t1.tenant_id == 1
    assert doc_t2.tenant_id == 2
    assert doc_t1.id != doc_t2.id