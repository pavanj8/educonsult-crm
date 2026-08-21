"""Tests for the ChecklistItemTemplate ORM model (E26 read-model side; E15 schema).

Exercises column shape, persistence, nullable ``program_id`` (NULL =
applies to all programs), and the snake_case stage value persistence
(parallel to ``test_application_stage_persists_snake_case_value``).
"""

from datetime import datetime, timezone

from sqlalchemy import inspect, select

from app.models.application import Application
from app.models.checklist_item_template import ChecklistItemTemplate
from app.models.program import Program
from app.pipeline.stages import PipelineStage


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_checklist_item_template_model_has_required_columns():
    column_names = {column.key for column in inspect(ChecklistItemTemplate).columns}
    assert column_names == {
        "id",
        "tenant_id",
        "stage",
        "program_id",
        "name",
        "description",
        "required",
        "order_index",
        "created_at",
        "updated_at",
    }


def test_checklist_item_template_persists_full_row(db_session):
    """A ChecklistItemTemplate row with every field populated round-trips."""
    now = _utc_now()
    program = Program(
        tenant_id=1,
        university_id=10,
        name="Computer Science MSc",
        created_at=now,
        updated_at=now,
    )
    db_session.add(program)
    db_session.commit()
    db_session.refresh(program)

    template = ChecklistItemTemplate(
        tenant_id=1,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=program.id,
        name="Passport copy",
        description="Color scan of the photo page",
        required=True,
        order_index=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    assert template.id is not None
    assert template.tenant_id == 1
    assert template.stage == PipelineStage.DOCUMENT_VERIFICATION
    assert template.program_id == program.id
    assert template.name == "Passport copy"
    assert template.description == "Color scan of the photo page"
    assert template.required is True
    assert template.order_index == 1
    assert template.created_at is not None
    assert template.updated_at is not None


def test_checklist_item_template_program_id_is_nullable_for_global_template(db_session):
    """Templates without a program_id apply to every program (Requirements §5)."""
    now = _utc_now()
    template = ChecklistItemTemplate(
        tenant_id=1,
        stage=PipelineStage.REGISTERED,
        program_id=None,
        name="Passport copy",
        required=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    assert template.program_id is None


def test_checklist_item_template_description_is_optional(db_session):
    """``description`` may be NULL for templates without longer guidance text."""
    now = _utc_now()
    template = ChecklistItemTemplate(
        tenant_id=1,
        stage=PipelineStage.REGISTERED,
        program_id=None,
        name="Passport copy",
        description=None,
        required=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    assert template.description is None


def test_checklist_item_template_required_defaults_to_true(db_session):
    """The default for ``required`` is True (most checklist items are required)."""
    now = _utc_now()
    template = ChecklistItemTemplate(
        tenant_id=1,
        stage=PipelineStage.REGISTERED,
        program_id=None,
        name="Passport copy",
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    assert template.required is True


def test_checklist_item_template_required_can_be_false(db_session):
    """``required`` can be False for optional checklist items."""
    now = _utc_now()
    template = ChecklistItemTemplate(
        tenant_id=1,
        stage=PipelineStage.REGISTERED,
        program_id=None,
        name="Recommendation letter",
        required=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    assert template.required is False


def test_checklist_item_template_order_index_is_nullable(db_session):
    """``order_index`` is nullable so a NULL means "append" in UI ordering."""
    now = _utc_now()
    template = ChecklistItemTemplate(
        tenant_id=1,
        stage=PipelineStage.REGISTERED,
        program_id=None,
        name="Passport copy",
        order_index=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    assert template.order_index is None


def test_checklist_item_template_persists_snake_case_stage_value(db_session):
    """Stage column stores the snake_case enum value (e.g. 'document_verification')."""
    now = _utc_now()
    template = ChecklistItemTemplate(
        tenant_id=1,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=None,
        name="Passport copy",
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()

    stored_stage = db_session.execute(
        select(ChecklistItemTemplate.__table__.c.stage).where(
            ChecklistItemTemplate.__table__.c.name == "Passport copy"
        )
    ).scalar_one()
    assert stored_stage == PipelineStage.DOCUMENT_VERIFICATION.value


def test_checklist_item_template_tenant_scoping(db_session):
    """Two tenants' templates coexist and are addressable by id."""
    now = _utc_now()
    template_t1 = ChecklistItemTemplate(
        tenant_id=1,
        stage=PipelineStage.REGISTERED,
        program_id=None,
        name="Passport copy (tenant 1)",
        created_at=now,
        updated_at=now,
    )
    template_t2 = ChecklistItemTemplate(
        tenant_id=2,
        stage=PipelineStage.REGISTERED,
        program_id=None,
        name="Passport copy (tenant 2)",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([template_t1, template_t2])
    db_session.commit()
    db_session.refresh(template_t1)
    db_session.refresh(template_t2)

    assert template_t1.tenant_id == 1
    assert template_t2.tenant_id == 2
    assert template_t1.id != template_t2.id


def test_checklist_item_template_fk_to_program(db_session):
    """FK to Program: a template may be narrowed to one program row."""
    now = _utc_now()
    program = Program(
        tenant_id=1,
        university_id=10,
        name="CS MSc",
        created_at=now,
        updated_at=now,
    )
    db_session.add(program)
    db_session.commit()
    db_session.refresh(program)

    template = ChecklistItemTemplate(
        tenant_id=1,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=program.id,
        name="Program-specific form",
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    assert template.program_id == program.id
    # And the application is unrelated; we just confirm the FK chain works.
    application = Application(
        tenant_id=1,
        student_id=99,
        university_id=10,
        program_id=program.id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    assert application.program_id == program.id
