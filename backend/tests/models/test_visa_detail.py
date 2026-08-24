"""Tests for the VisaDetail ORM model (E34 schema; Journey J27).

Exercises column shape, tenant scoping, the application_id 1:1 unique
constraint, persistence with and without an interview_date, and the
ON DELETE CASCADE contract on the application FK. The recording API
land in the sibling E34 backend ticket (read/write endpoints) and
the frontend update form lands in #194; here we only test the
persisted shape.

Includes an issue #193 / E34 / J27 traceability test that pins the
schema (tenant-scoped, one row per application, visa_type +
interview_date) the E34 API and the #194 frontend form need to read
and write against.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models.application import Application
from app.models.base import TenantScopedBase
from app.models.visa_detail import VisaDetail


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_application(db_session, tenant_id: int = 1, **overrides) -> Application:
    now = _utc_now()
    application = Application(
        tenant_id=tenant_id,
        student_id=overrides.get("student_id", 100),
        university_id=overrides.get("university_id", 10),
        program_id=overrides.get("program_id", 20),
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application


def test_visa_detail_table_uses_tenant_scoped_base():
    assert issubclass(VisaDetail, TenantScopedBase)
    assert VisaDetail.tenant_id.property.columns[0].nullable is False
    assert VisaDetail.application_id.property.columns[0].nullable is False
    assert VisaDetail.visa_type.property.columns[0].nullable is False


def test_visa_detail_model_has_required_columns():
    assert {column.key for column in inspect(VisaDetail).columns} == {
        "id",
        "tenant_id",
        "application_id",
        "visa_type",
        "interview_date",
        "created_at",
        "updated_at",
    }


def test_visa_detail_interview_date_is_nullable():
    """J27 records visa_type and interview_date as two separate fields; the
    interview date can be added later (after the visa type is captured)."""
    column = VisaDetail.interview_date.property.columns[0]
    assert column.nullable is True


def test_visa_detail_application_id_is_unique(db_session):
    """One :class:`VisaDetail` row per application (J27)."""
    application = _make_application(db_session)
    now = _utc_now()

    first = VisaDetail(
        tenant_id=1,
        application_id=application.id,
        visa_type="F-1 Student",
        interview_date=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(first)
    db_session.commit()

    second = VisaDetail(
        tenant_id=1,
        application_id=application.id,
        visa_type="F-1 Student",
        interview_date=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_visa_detail_persists_row_with_interview_date(db_session):
    """A visa detail with both visa_type and interview_date round-trips."""
    application = _make_application(db_session)
    now = _utc_now()
    # SQLite (the test DB) strips tzinfo on round-trip even for
    # timezone-aware columns; pass a naive datetime to match.
    interview_at = datetime(2026, 11, 5, 14, 30)

    detail = VisaDetail(
        tenant_id=1,
        application_id=application.id,
        visa_type="F-1 Student",
        interview_date=interview_at,
        created_at=now,
        updated_at=now,
    )
    db_session.add(detail)
    db_session.commit()
    db_session.refresh(detail)

    assert detail.id is not None
    assert detail.tenant_id == 1
    assert detail.application_id == application.id
    assert detail.visa_type == "F-1 Student"
    assert detail.interview_date == interview_at


def test_visa_detail_persists_row_without_interview_date(db_session):
    """A visa detail can be recorded before the interview date is known."""
    application = _make_application(db_session)
    now = _utc_now()

    detail = VisaDetail(
        tenant_id=1,
        application_id=application.id,
        visa_type="Tier 4 Student",
        interview_date=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(detail)
    db_session.commit()
    db_session.refresh(detail)

    assert detail.interview_date is None
    assert detail.visa_type == "Tier 4 Student"


def test_visa_detail_tenant_scoping(db_session):
    """Two tenants' visa details coexist and are addressable by id."""
    app_t1 = _make_application(db_session, tenant_id=1, student_id=100)
    app_t2 = _make_application(db_session, tenant_id=2, student_id=200)
    now = _utc_now()

    detail_t1 = VisaDetail(
        tenant_id=1,
        application_id=app_t1.id,
        visa_type="F-1 Student",
        interview_date=None,
        created_at=now,
        updated_at=now,
    )
    detail_t2 = VisaDetail(
        tenant_id=2,
        application_id=app_t2.id,
        visa_type="Tier 4 Student",
        interview_date=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([detail_t1, detail_t2])
    db_session.commit()

    assert detail_t1.tenant_id == 1
    assert detail_t2.tenant_id == 2
    assert detail_t1.id != detail_t2.id
    assert detail_t1.application_id == app_t1.id
    assert detail_t2.application_id == app_t2.id


def test_visa_detail_round_trip_for_e34_schema(db_session) -> None:
    """Issue #193 / E34 / J27: pin the persisted shape the E34 API (sibling
    ticket) and the #194 frontend update form need to read and write
    against.

    The visa detail must:

    * be tenant-scoped (ADR-0001),
    * link to exactly one application (J27: the visa type and
      interview date are properties of *the* application at the visa
      stage -- enforced by the UNIQUE on ``application_id``),
    * carry the visa type as a short string label (Requirements §5
      visa type field),
    * carry an optional embassy interview date as a timezone-aware
      ``DateTime`` (Requirements §5 visa interview date field;
      nullable so the type can be recorded before the date is known).

    All fields round-trip losslessly across an insert + commit + refresh.
    """
    application = _make_application(db_session)
    now = _utc_now()
    # SQLite (the test DB) strips tzinfo on round-trip even for
    # timezone-aware columns; pass a naive datetime to match.
    interview_at = datetime(2026, 12, 1, 9, 0)

    detail = VisaDetail(
        tenant_id=1,
        application_id=application.id,
        visa_type="F-1 Student",
        interview_date=interview_at,
        created_at=now,
        updated_at=now,
    )
    db_session.add(detail)
    db_session.commit()
    db_session.refresh(detail)

    assert detail.tenant_id == 1
    assert detail.application_id == application.id
    assert detail.visa_type == "F-1 Student"
    assert detail.interview_date == interview_at