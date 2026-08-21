"""Tests for the StageHistory ORM model (E25; Journey J18).

Exercises column shape, persistence, the nullable ``from_stage`` for the
initial provenance row, and the snake_case stage value persistence
(parallel to the existing ``test_application_stage_persists_snake_case_value``
test so the history log stays consistent with the ``applications.stage``
column).
"""

from datetime import datetime, timezone

from sqlalchemy import inspect, select

from app.models.application import Application
from app.models.stage_history import StageHistory
from app.pipeline.stages import PipelineStage


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_stage_history_model_has_required_columns():
    column_names = {column.key for column in inspect(StageHistory).columns}
    assert column_names == {
        "id",
        "tenant_id",
        "application_id",
        "from_stage",
        "to_stage",
        "changed_by_user_id",
        "changed_at",
        "reason",
        "created_at",
        "updated_at",
    }


def test_stage_history_persists_full_row(db_session):
    """A StageHistory row with every field populated round-trips through the DB."""
    now = _utc_now()
    application = Application(
        tenant_id=1,
        student_id=10,
        university_id=100,
        program_id=200,
        stage=PipelineStage.COUNSELING,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    history = StageHistory(
        tenant_id=1,
        application_id=application.id,
        from_stage=PipelineStage.REGISTERED,
        to_stage=PipelineStage.COUNSELING,
        changed_by_user_id=42,
        changed_at=now,
        reason=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(history)
    db_session.commit()
    db_session.refresh(history)

    assert history.id is not None
    assert history.tenant_id == 1
    assert history.application_id == application.id
    assert history.from_stage == PipelineStage.REGISTERED
    assert history.to_stage == PipelineStage.COUNSELING
    assert history.changed_by_user_id == 42
    # SQLite drops the tzinfo on round-trip; compare the absolute UTC instant.
    assert history.changed_at.replace(tzinfo=timezone.utc) == now
    assert history.reason is None
    assert history.created_at is not None
    assert history.updated_at is not None


def test_stage_history_from_stage_is_nullable_for_initial_row(db_session):
    """The first history row for an application has ``from_stage`` NULL (initial provenance)."""
    now = _utc_now()
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

    history = StageHistory(
        tenant_id=1,
        application_id=application.id,
        from_stage=None,
        to_stage=PipelineStage.REGISTERED,
        changed_by_user_id=None,
        changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(history)
    db_session.commit()
    db_session.refresh(history)

    assert history.from_stage is None
    assert history.to_stage == PipelineStage.REGISTERED
    assert history.changed_by_user_id is None
    assert history.reason is None


def test_stage_history_changed_by_user_id_is_nullable(db_session):
    """``changed_by_user_id`` is nullable so the column survives staff deletion (SET NULL)."""
    now = _utc_now()
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

    history = StageHistory(
        tenant_id=1,
        application_id=application.id,
        from_stage=PipelineStage.REGISTERED,
        to_stage=PipelineStage.COUNSELING,
        changed_by_user_id=None,
        changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(history)
    db_session.commit()
    db_session.refresh(history)

    assert history.changed_by_user_id is None


def test_stage_history_reason_is_optional(db_session):
    """``reason`` is NULL for ordinary forward moves and populated for terminal rejections."""
    now = _utc_now()
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

    forward = StageHistory(
        tenant_id=1,
        application_id=application.id,
        from_stage=PipelineStage.REGISTERED,
        to_stage=PipelineStage.COUNSELING,
        changed_at=now,
        created_at=now,
        updated_at=now,
    )
    rejected = StageHistory(
        tenant_id=1,
        application_id=application.id,
        from_stage=PipelineStage.COUNSELING,
        to_stage=PipelineStage.REJECTED,
        changed_at=now,
        reason="Student did not meet academic requirements",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([forward, rejected])
    db_session.commit()
    db_session.refresh(forward)
    db_session.refresh(rejected)

    assert forward.reason is None
    assert rejected.reason == "Student did not meet academic requirements"


def test_stage_history_persists_snake_case_stage_values(db_session):
    """Stage columns store the snake_case enum value (e.g. 'document_verification')."""
    now = _utc_now()
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

    history = StageHistory(
        tenant_id=1,
        application_id=application.id,
        from_stage=PipelineStage.DOCUMENT_VERIFICATION,
        to_stage=PipelineStage.OFFER_LETTER,
        changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(history)
    db_session.commit()

    stored_from = db_session.execute(
        select(StageHistory.__table__.c.from_stage).where(
            StageHistory.__table__.c.to_stage == PipelineStage.OFFER_LETTER.value
        )
    ).scalar_one()
    stored_to = db_session.execute(
        select(StageHistory.__table__.c.to_stage).where(
            StageHistory.__table__.c.from_stage == PipelineStage.DOCUMENT_VERIFICATION.value
        )
    ).scalar_one()
    assert stored_from == PipelineStage.DOCUMENT_VERIFICATION.value
    assert stored_to == PipelineStage.OFFER_LETTER.value


def test_stage_history_initial_row_with_null_from_round_trips(db_session):
    """The transition ``None -> REGISTERED`` is representable (initial provenance row)."""
    now = _utc_now()
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

    history = StageHistory(
        tenant_id=1,
        application_id=application.id,
        from_stage=None,
        to_stage=PipelineStage.REGISTERED,
        changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(history)
    db_session.commit()

    stored_from = db_session.execute(
        select(StageHistory.__table__.c.from_stage).where(
            StageHistory.__table__.c.application_id == application.id
        )
    ).scalar_one()
    stored_to = db_session.execute(
        select(StageHistory.__table__.c.to_stage).where(
            StageHistory.__table__.c.application_id == application.id
        )
    ).scalar_one()
    assert stored_from is None
    assert stored_to == PipelineStage.REGISTERED.value
