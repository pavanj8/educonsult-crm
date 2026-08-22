"""Default baseline master data (E14; Journey J7).

Provides a canonical, platform-default list of countries / universities
/ programs that new tenants can be seeded with as a sensible starting
point for their study-abroad dropdowns. The list is intentionally
small but covers the most common study destinations so a newly
provisioned consultancy is usable end-to-end on day one without the
owner/branch manager having to hand-curate every dropdown entry
before a student can self-register (Journey J9 — structured dropdowns)
or create an application (Journey J11).

Design
------
* The default list lives here as plain data (``DEFAULT_COUNTRIES``,
  ``DEFAULT_UNIVERSITIES``, ``DEFAULT_PROGRAMS``) and is the single
  source of truth for tests, the seed CLI, and any future tenant
  provisioning hook.
* ``seed_default_master_data_for_tenant`` inserts the defaults for a
  specific tenant. It is **idempotent**: rows already present for the
  tenant (matched by ``(name, code)`` for countries, ``(name,
  country_id)`` for universities, ``(name, university_id)`` for
  programs) are skipped, so re-running it is safe and does not produce
  duplicate dropdown options.
* Cross-tenant safety: defaults are always inserted with the supplied
  ``tenant_id``; the function never falls back to the caller or to a
  platform-wide row. A tenant's defaults never bleed into another
  tenant's master data.

Traceability
------------
* Requirements §5 (structured admin-managed master list of target
  country / university / program).
* Journey J7 (Owner/Branch Manager manages master data).
* Epic E14 (Master Data Management); this module is the seed half
  of the epic, complementing the CRUD router
  (:mod:`app.routers.master_data_admin`), the public list router
  (:mod:`app.routers.master_data`), and the master-data admin UI
  (sibling ticket #128).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.country import Country
from app.models.program import Program
from app.models.university import University


def _utc_now() -> datetime:
    """Return a timezone-aware UTC ``datetime`` (portable across SQL dialects)."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DefaultCountry:
    """Canonical country option used as the platform-default seed."""

    name: str
    code: str


@dataclass(frozen=True, slots=True)
class DefaultUniversity:
    """Canonical university option scoped to a ``DefaultCountry.name``.

    The reference to the country is by name (not by id) so the dataset
    stays stable across re-seeds: ids are assigned at insert time and
    the seeder resolves them by looking up the country that was just
    inserted for the same tenant.
    """

    country_name: str
    name: str


@dataclass(frozen=True, slots=True)
class DefaultProgram:
    """Canonical program option scoped to a ``DefaultUniversity.name``."""

    university_name: str
    name: str


# Canonical platform defaults. Each tier references the tier above by
# *name* (not by id) so the catalog is self-describing and ids are
# assigned at insert time. The list is intentionally short: enough
# coverage for the most common study-abroad destinations so a fresh
# tenant's dropdowns are usable end-to-end, but not so large that
# duplicating it per tenant becomes wasteful.
DEFAULT_COUNTRIES: tuple[DefaultCountry, ...] = (
    DefaultCountry(name="Canada", code="CA"),
    DefaultCountry(name="United Kingdom", code="GB"),
    DefaultCountry(name="Australia", code="AU"),
    DefaultCountry(name="United States", code="US"),
    DefaultCountry(name="Germany", code="DE"),
)


DEFAULT_UNIVERSITIES: tuple[DefaultUniversity, ...] = (
    DefaultUniversity(country_name="Canada", name="University of Toronto"),
    DefaultUniversity(country_name="Canada", name="University of British Columbia"),
    DefaultUniversity(country_name="United Kingdom", name="University of Manchester"),
    DefaultUniversity(country_name="United Kingdom", name="University of Edinburgh"),
    DefaultUniversity(country_name="Australia", name="University of Melbourne"),
    DefaultUniversity(country_name="Australia", name="Monash University"),
    DefaultUniversity(country_name="United States", name="Stanford University"),
    DefaultUniversity(country_name="United States", name="Massachusetts Institute of Technology"),
    DefaultUniversity(country_name="Germany", name="Technical University of Munich"),
)


DEFAULT_PROGRAMS: tuple[DefaultProgram, ...] = (
    DefaultProgram(university_name="University of Toronto", name="Computer Science MSc"),
    DefaultProgram(university_name="University of Toronto", name="Business Administration MBA"),
    DefaultProgram(
        university_name="University of British Columbia",
        name="Data Science MSc",
    ),
    DefaultProgram(
        university_name="University of Manchester",
        name="Mechanical Engineering MSc",
    ),
    DefaultProgram(
        university_name="University of Edinburgh",
        name="Artificial Intelligence MSc",
    ),
    DefaultProgram(
        university_name="University of Melbourne",
        name="Public Health MPH",
    ),
    DefaultProgram(university_name="Monash University", name="Pharmacy MPharm"),
    DefaultProgram(university_name="Stanford University", name="Computer Science MSc"),
    DefaultProgram(
        university_name="Massachusetts Institute of Technology",
        name="Electrical Engineering MSc",
    ),
    DefaultProgram(
        university_name="Technical University of Munich",
        name="Robotics MSc",
    ),
)


def _validate_default_catalog() -> None:
    """Raise ``ValueError`` if the default catalog is internally inconsistent.

    Run at import time so any structural problem in the defaults
    surfaces immediately (e.g. a university that names an unknown
    country, or a program that names an unknown university). This is
    cheaper than discovering the problem at seed time deep inside a
    long-running batch insert.
    """
    country_names = {country.name for country in DEFAULT_COUNTRIES}
    university_names = {university.name for university in DEFAULT_UNIVERSITIES}
    for university in DEFAULT_UNIVERSITIES:
        if university.country_name not in country_names:
            raise ValueError(
                f"default university {university.name!r} references unknown "
                f"country {university.country_name!r}"
            )
    for program in DEFAULT_PROGRAMS:
        if program.university_name not in university_names:
            raise ValueError(
                f"default program {program.name!r} references unknown "
                f"university {program.university_name!r}"
            )


_validate_default_catalog()


@dataclass(frozen=True, slots=True)
class DefaultMasterDataSeedResult:
    """Summary of what ``seed_default_master_data_for_tenant`` inserted.

    The ``*_inserted`` counts report only the rows that were newly
    created by the call; rows that were already present (and therefore
    skipped for idempotency) are reflected by the difference between
    the inserted count and the corresponding ``len`` of the default
    catalog. This lets tests and ops verify the call did the work they
    expected without having to re-derive it from the catalog size.
    """

    tenant_id: int
    countries_inserted: int
    universities_inserted: int
    programs_inserted: int


def _existing_country_names(db: Session, tenant_id: int) -> set[str]:
    """Return the set of country names already present for ``tenant_id``."""
    return {
        row[0]
        for row in db.query(Country.name).filter(Country.tenant_id == tenant_id).all()
    }


def _existing_university_keys(db: Session, tenant_id: int) -> set[tuple[str, int]]:
    """Return ``(name, country_id)`` tuples already present for ``tenant_id``."""
    return {
        (row.name, row.country_id)
        for row in db.query(University)
        .filter(University.tenant_id == tenant_id)
        .all()
    }


def _existing_program_keys(db: Session, tenant_id: int) -> set[tuple[str, int]]:
    """Return ``(name, university_id)`` tuples already present for ``tenant_id``."""
    return {
        (row.name, row.university_id)
        for row in db.query(Program).filter(Program.tenant_id == tenant_id).all()
    }


def seed_default_master_data_for_tenant(
    db: Session,
    tenant_id: int,
) -> DefaultMasterDataSeedResult:
    """Insert the default master data for ``tenant_id`` (idempotent).

    Behaviour
    ---------
    * Rows already present for the tenant are skipped so re-running the
      seeder (e.g. on every app boot) does not create duplicates.
    * All rows are inserted with ``tenant_id`` set to ``tenant_id``;
      the function never touches another tenant's data.
    * On any exception the session is rolled back so partial inserts
      do not leak into the database.

    Raises
    ------
    ValueError
        If ``tenant_id`` is not a positive integer. The constraint
        catches the obvious caller-side bug at the seed boundary
        rather than letting it surface as an opaque FK or NOT NULL
        failure deeper in the stack.
    """
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise ValueError("tenant_id must be a positive integer")

    now = _utc_now()

    # --- Countries ----------------------------------------------------
    existing_country_names = _existing_country_names(db, tenant_id)
    countries_to_insert = [
        country
        for country in DEFAULT_COUNTRIES
        if country.name not in existing_country_names
    ]
    if countries_to_insert:
        db.bulk_save_objects(
            [
                Country(
                    tenant_id=tenant_id,
                    name=country.name,
                    code=country.code,
                    created_at=now,
                    updated_at=now,
                )
                for country in countries_to_insert
            ],
        )
        db.flush()

    # Re-read the inserted countries keyed by name -> id so we can
    # resolve universities by their ``country_name`` reference.
    country_id_by_name = {
        row.name: row.id
        for row in db.query(Country).filter(Country.tenant_id == tenant_id).all()
    }

    # --- Universities -------------------------------------------------
    existing_university_keys = _existing_university_keys(db, tenant_id)
    universities_to_insert = [
        university
        for university in DEFAULT_UNIVERSITIES
        if (
            university.name,
            country_id_by_name[university.country_name],
        )
        not in existing_university_keys
    ]
    if universities_to_insert:
        db.bulk_save_objects(
            [
                University(
                    tenant_id=tenant_id,
                    country_id=country_id_by_name[university.country_name],
                    name=university.name,
                    created_at=now,
                    updated_at=now,
                )
                for university in universities_to_insert
            ],
        )
        db.flush()

    # Re-read inserted universities keyed by name -> id so we can
    # resolve programs by their ``university_name`` reference.
    university_id_by_name = {
        row.name: row.id
        for row in db.query(University).filter(University.tenant_id == tenant_id).all()
    }

    # --- Programs -----------------------------------------------------
    existing_program_keys = _existing_program_keys(db, tenant_id)
    programs_to_insert = [
        program
        for program in DEFAULT_PROGRAMS
        if (program.name, university_id_by_name[program.university_name])
        not in existing_program_keys
    ]
    if programs_to_insert:
        db.bulk_save_objects(
            [
                Program(
                    tenant_id=tenant_id,
                    university_id=university_id_by_name[program.university_name],
                    name=program.name,
                    created_at=now,
                    updated_at=now,
                )
                for program in programs_to_insert
            ],
        )
        db.flush()

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return DefaultMasterDataSeedResult(
        tenant_id=tenant_id,
        countries_inserted=len(countries_to_insert),
        universities_inserted=len(universities_to_insert),
        programs_inserted=len(programs_to_insert),
    )