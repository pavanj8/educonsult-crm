from datetime import datetime, timezone

<<<<<<< HEAD
from sqlalchemy import inspect, select

from app.models.application import Application, ApplicationStage
=======
from sqlalchemy import inspect

from app.models.application import Application
from app.pipeline.stages import PipelineStage
>>>>>>> origin/main


def test_application_model_has_required_columns():
    column_names = {column.key for column in inspect(Application).columns}
    assert column_names == {
        "id",
        "tenant_id",
        "student_id",
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
        student_id=10,
<<<<<<< HEAD
        university_id=20,
        program_id=30,
        stage=ApplicationStage.REGISTERED,
=======
        university_id=100,
        program_id=200,
        stage=PipelineStage.REGISTERED,
>>>>>>> origin/main
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    assert application.id is not None
<<<<<<< HEAD
    assert application.tenant_id == 1
    assert application.student_id == 10
    assert application.university_id == 20
    assert application.program_id == 30
    assert application.stage == ApplicationStage.REGISTERED
    assert application.created_at is not None
    assert application.updated_at is not None


def test_application_stage_defaults_to_registered(db_session):
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=20,
        program_id=30,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    assert application.stage == ApplicationStage.REGISTERED


def test_application_stage_persists_snake_case_value(db_session):
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=20,
        program_id=30,
        stage=ApplicationStage.DOCUMENT_VERIFICATION,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()

    stored_stage = db_session.execute(
        select(Application.__table__.c.stage).where(Application.__table__.c.student_id == 10)
    ).scalar_one()
    assert stored_stage == ApplicationStage.DOCUMENT_VERIFICATION.value


def test_student_can_have_multiple_applications_with_independent_stages(db_session):
    now = datetime.now(timezone.utc)
    first = Application(
        tenant_id=1,
        student_id=10,
        university_id=20,
        program_id=30,
        stage=ApplicationStage.COUNSELING,
        created_at=now,
        updated_at=now,
    )
    second = Application(
        tenant_id=1,
        student_id=10,
        university_id=21,
        program_id=31,
        stage=ApplicationStage.APPLICATION_SUBMITTED,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([first, second])
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)

    assert first.id != second.id
    assert first.stage == ApplicationStage.COUNSELING
    assert second.stage == ApplicationStage.APPLICATION_SUBMITTED
=======
    assert application.stage == PipelineStage.REGISTERED
>>>>>>> origin/main
