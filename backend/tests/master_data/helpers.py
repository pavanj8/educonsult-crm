"""Master data test helpers."""

from datetime import datetime, timezone

from app.models.country import Country
from app.models.program import Program
from app.models.university import University


def seed_country(
    db_session,
    *,
    tenant_id: int,
    name: str = "Canada",
    code: str = "CA",
) -> Country:
    now = datetime.now(timezone.utc)
    country = Country(
        tenant_id=tenant_id,
        name=name,
        code=code,
        created_at=now,
        updated_at=now,
    )
    db_session.add(country)
    db_session.commit()
    db_session.refresh(country)
    return country


def seed_university(
    db_session,
    *,
    tenant_id: int,
    country_id: int,
    name: str = "University of Toronto",
) -> University:
    now = datetime.now(timezone.utc)
    university = University(
        tenant_id=tenant_id,
        country_id=country_id,
        name=name,
        created_at=now,
        updated_at=now,
    )
    db_session.add(university)
    db_session.commit()
    db_session.refresh(university)
    return university


def seed_program(
    db_session,
    *,
    tenant_id: int,
    university_id: int,
    name: str = "Computer Science MSc",
) -> Program:
    now = datetime.now(timezone.utc)
    program = Program(
        tenant_id=tenant_id,
        university_id=university_id,
        name=name,
        created_at=now,
        updated_at=now,
    )
    db_session.add(program)
    db_session.commit()
    db_session.refresh(program)
    return program


def seed_master_data_chain(db_session, *, tenant_id: int) -> tuple[Country, University, Program]:
    country = seed_country(db_session, tenant_id=tenant_id)
    university = seed_university(
        db_session,
        tenant_id=tenant_id,
        country_id=country.id,
    )
    program = seed_program(
        db_session,
        tenant_id=tenant_id,
        university_id=university.id,
    )
    return country, university, program
