from datetime import datetime, timezone

from sqlalchemy import inspect, select

from app.models.application import Application
from app.pipeline.stages import PipelineStage


def test_application_model_has_required_columns():
    column_names = {column.key for column in inspect(Application).columns}
    assert column_names == {
        "assigned_counselor_id",
        "created_at",
        "enrollment_date",
        "id",
        "loan_amount",
        "loan_lender",
        "loan_opted_in",
        "loan_status",
        "program_id",
        "stage",
        "stage_reason",
        "student_id",
        "target_program_id",
        "target_university_id",
        "tenant_id",
        "university_id",
        "updated_at",
    }


def test_application_persists_row(db_session):
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
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
    assert application.student_id == 10
    assert application.university_id == 100
    assert application.program_id == 200
    assert application.stage == PipelineStage.REGISTERED
    assert application.created_at is not None
    assert application.updated_at is not None


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


def test_application_loan_opted_in_defaults_to_false(db_session):
    """The loan_opted_in column defaults to False (boolean, not int 0)."""
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

    assert application.loan_opted_in is False


def test_application_loan_opted_in_round_trips_as_bool(db_session):
    """``loan_opted_in=True`` round-trips as a real bool on read.

    Guards against the type lie where the column was declared as Integer and
    silently returned 0/1 ints at the ORM boundary.
    """
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=100,
        program_id=200,
        loan_opted_in=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    assert application.loan_opted_in is True


def test_application_university_and_program_are_required(db_session):
    """``university_id`` and ``program_id`` are NOT NULL (E18 contract)."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=None,
        program_id=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_application_terminal_stage_reason_is_persisted(db_session):
    """The optional ``stage_reason`` column captures why a terminal stage was chosen (J32/J33)."""
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=100,
        program_id=200,
        stage=PipelineStage.REJECTED,
        stage_reason="Insufficient academic record",
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    assert application.stage == PipelineStage.REJECTED
    assert application.stage_reason == "Insufficient academic record"


def test_application_enrollment_date_is_persisted(db_session):
    """The optional ``enrollment_date`` column records when an Enrolled transition happened (J31)."""
    now = datetime.now(timezone.utc)
    enrolled_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=100,
        program_id=200,
        stage=PipelineStage.ENROLLED,
        enrollment_date=enrolled_at,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    assert application.enrollment_date == enrolled_at


def test_application_assigned_counselor_defaults_to_none(db_session):
    """A fresh application has no assigned counselor until round-robin runs (E19)."""
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

    assert application.assigned_counselor_id is None
