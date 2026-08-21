"""Tests for the Application ORM model (E18; E21; Requirements §5).

Exercises column shape, persistence, stage default, and the multiple-
applications-per-student invariant for Journey J11 / J14.
"""

from datetime import datetime, timezone

from sqlalchemy import inspect, select

from app.models.application import Application
from app.pipeline.stages import PipelineStage


def test_application_model_has_required_columns():
    column_names = {column.key for column in inspect(Application).columns}
    assert column_names == {
        "id",
        "tenant_id",
        "branch_id",
        "student_id",
        "assigned_counselor_id",
        "university_id",
        "program_id",
        "stage",
        "created_at",
        "updated_at",
    }


def test_application_persists_row(db_session):
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        branch_id=2,
        student_id=10,
        assigned_counselor_id=11,
        university_id=100,
        program_id=200,
        stage=PipelineStage.REGISTERED,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    assert application.id is not None
    assert application.tenant_id == 1
    assert application.branch_id == 2
    assert application.student_id == 10
    assert application.assigned_counselor_id == 11
    assert application.university_id == 100
    assert application.program_id == 200
    assert application.stage == PipelineStage.REGISTERED
    assert application.created_at is not None
    assert application.updated_at is not None


def test_application_branch_and_counselor_are_nullable(db_session):
    """E18 rows pre-date E21, so ``branch_id`` and ``assigned_counselor_id`` are nullable.

    E19 (auto-assignment) and E20 (manual reassignment) will populate them
    and tighten the constraints; until then a fresh Application can be
    created with both columns ``NULL`` (matching the ORM model and the
    E18 ``create_application`` code path).
    """
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=100,
        program_id=200,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    assert application.branch_id is None
    assert application.assigned_counselor_id is None


def test_application_stage_defaults_to_registered(db_session):
    """A newly-created application defaults to the REGISTERED pipeline stage (J11)."""
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=100,
        program_id=200,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    assert application.stage == PipelineStage.REGISTERED


def test_application_stage_persists_snake_case_value(db_session):
    """The stage column stores the snake_case enum value (e.g. 'document_verification')."""
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=100,
        program_id=200,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()

    stored_stage = db_session.execute(
        select(Application.__table__.c.stage).where(Application.__table__.c.student_id == 10)
    ).scalar_one()
    assert stored_stage == PipelineStage.DOCUMENT_VERIFICATION.value


def test_student_can_have_multiple_applications_with_independent_stages(db_session):
    """A student can have multiple applications, each with its own pipeline stage (J11)."""
    now = datetime.now(timezone.utc)
    first = Application(
        tenant_id=1,
        student_id=10,
        university_id=100,
        program_id=200,
        stage=PipelineStage.COUNSELING,
        created_at=now,
        updated_at=now,
    )
    second = Application(
        tenant_id=1,
        student_id=10,
        university_id=101,
        program_id=201,
        stage=PipelineStage.APPLICATION_SUBMITTED,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([first, second])
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)

    assert first.id != second.id
    assert first.stage == PipelineStage.COUNSELING
    assert second.stage == PipelineStage.APPLICATION_SUBMITTED
