"""Tests for the default master-data seed (E14; Journey J7; issue #129).

Covers:

* the structural well-formedness of ``DEFAULT_COUNTRIES``,
  ``DEFAULT_UNIVERSITIES``, and ``DEFAULT_PROGRAMS``;
* the behavior of ``seed_default_master_data_for_tenant`` when applied
  to a brand-new tenant (inserts exactly the canonical rows);
* idempotency: re-running the seeder for the same tenant must not
  create duplicates and must leave existing rows untouched;
* tenant isolation: defaults seeded for one tenant do not appear for
  another tenant, even after re-seeding both;
* integration with the public list endpoint
  (``GET /tenants/{slug}/countries``, ``.../universities``,
  ``.../programs``): a tenant whose defaults have been seeded serves
  those defaults through the public read endpoints without any
  additional admin CRUD traffic.
"""

from __future__ import annotations

import pytest

from app.models.country import Country
from app.models.program import Program
from app.models.tenant import Tenant
from app.models.university import University
from app.seed.master_data import (
    DEFAULT_COUNTRIES,
    DEFAULT_PROGRAMS,
    DEFAULT_UNIVERSITIES,
    DefaultCountry,
    DefaultMasterDataSeedResult,
    DefaultProgram,
    DefaultUniversity,
    seed_default_master_data_for_tenant,
)


# ---------------------------------------------------------------------------
# Constants: structural well-formedness
# ---------------------------------------------------------------------------


def test_default_countries_are_non_empty_and_unique() -> None:
    assert len(DEFAULT_COUNTRIES) >= 3
    names = [country.name for country in DEFAULT_COUNTRIES]
    codes = [country.code for country in DEFAULT_COUNTRIES]
    assert len(names) == len(set(names))
    assert len(codes) == len(set(codes))
    for country in DEFAULT_COUNTRIES:
        assert isinstance(country, DefaultCountry)
        assert country.name
        assert country.code
        assert country.code == country.code.upper()


def test_default_universities_reference_known_countries() -> None:
    country_names = {country.name for country in DEFAULT_COUNTRIES}
    assert len(DEFAULT_UNIVERSITIES) >= 3
    names = [university.name for university in DEFAULT_UNIVERSITIES]
    assert len(names) == len(set(names))
    for university in DEFAULT_UNIVERSITIES:
        assert isinstance(university, DefaultUniversity)
        assert university.country_name in country_names
        assert university.name


def test_default_programs_reference_known_universities() -> None:
    university_names = {university.name for university in DEFAULT_UNIVERSITIES}
    assert len(DEFAULT_PROGRAMS) >= 3
    # Programs may share a name across different universities (e.g. "Computer
    # Science MSc" offered by both UofT and Stanford), so uniqueness is
    # scoped to the (university_name, program_name) tuple, not just name.
    keys = [(program.university_name, program.name) for program in DEFAULT_PROGRAMS]
    assert len(keys) == len(set(keys))
    for program in DEFAULT_PROGRAMS:
        assert isinstance(program, DefaultProgram)
        assert program.university_name in university_names
        assert program.name


def test_default_catalog_has_no_orphan_universities_or_programs() -> None:
    """Every tier references the tier above by a real name (import-time check)."""
    country_names = {country.name for country in DEFAULT_COUNTRIES}
    university_names = {university.name for university in DEFAULT_UNIVERSITIES}
    for university in DEFAULT_UNIVERSITIES:
        assert university.country_name in country_names
    for program in DEFAULT_PROGRAMS:
        assert program.university_name in university_names


# ---------------------------------------------------------------------------
# seed_default_master_data_for_tenant: behavior on a fresh tenant
# ---------------------------------------------------------------------------


def _create_tenant(db_session, *, slug: str, name: str | None = None) -> Tenant:
    tenant = Tenant(name=name or slug.title(), slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_seed_inserts_all_defaults_for_a_fresh_tenant(db_session) -> None:
    tenant = _create_tenant(db_session, slug="apex")

    result = seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    assert isinstance(result, DefaultMasterDataSeedResult)
    assert result.tenant_id == tenant.id
    assert result.countries_inserted == len(DEFAULT_COUNTRIES)
    assert result.universities_inserted == len(DEFAULT_UNIVERSITIES)
    assert result.programs_inserted == len(DEFAULT_PROGRAMS)

    countries = (
        db_session.query(Country).filter(Country.tenant_id == tenant.id).all()
    )
    universities = (
        db_session.query(University).filter(University.tenant_id == tenant.id).all()
    )
    programs = (
        db_session.query(Program).filter(Program.tenant_id == tenant.id).all()
    )

    assert {country.name for country in countries} == {
        country.name for country in DEFAULT_COUNTRIES
    }
    assert {country.code for country in countries} == {
        country.code for country in DEFAULT_COUNTRIES
    }
    assert {university.name for university in universities} == {
        university.name for university in DEFAULT_UNIVERSITIES
    }
    assert {program.name for program in programs} == {
        program.name for program in DEFAULT_PROGRAMS
    }


def test_seed_assigns_unique_ids_per_tenant(db_session) -> None:
    tenant_a = _create_tenant(db_session, slug="apex")
    tenant_b = _create_tenant(db_session, slug="globalreach")

    seed_default_master_data_for_tenant(db_session, tenant_id=tenant_a.id)
    seed_default_master_data_for_tenant(db_session, tenant_id=tenant_b.id)

    country_ids_a = {
        row.id
        for row in db_session.query(Country)
        .filter(Country.tenant_id == tenant_a.id)
        .all()
    }
    country_ids_b = {
        row.id
        for row in db_session.query(Country)
        .filter(Country.tenant_id == tenant_b.id)
        .all()
    }
    assert country_ids_a.isdisjoint(country_ids_b)


def test_seed_universities_point_at_tenant_local_countries(db_session) -> None:
    tenant = _create_tenant(db_session, slug="apex")

    seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    tenant_country_ids = {
        row.id
        for row in db_session.query(Country)
        .filter(Country.tenant_id == tenant.id)
        .all()
    }
    universities = (
        db_session.query(University).filter(University.tenant_id == tenant.id).all()
    )
    for university in universities:
        assert university.country_id in tenant_country_ids


def test_seed_programs_point_at_tenant_local_universities(db_session) -> None:
    tenant = _create_tenant(db_session, slug="apex")

    seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    tenant_university_ids = {
        row.id
        for row in db_session.query(University)
        .filter(University.tenant_id == tenant.id)
        .all()
    }
    programs = (
        db_session.query(Program).filter(Program.tenant_id == tenant.id).all()
    )
    for program in programs:
        assert program.university_id in tenant_university_ids


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_seed_is_idempotent_for_a_tenant_already_seeded(db_session) -> None:
    tenant = _create_tenant(db_session, slug="apex")

    first = seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)
    second = seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    assert first.countries_inserted == len(DEFAULT_COUNTRIES)
    assert first.universities_inserted == len(DEFAULT_UNIVERSITIES)
    assert first.programs_inserted == len(DEFAULT_PROGRAMS)
    assert second.countries_inserted == 0
    assert second.universities_inserted == 0
    assert second.programs_inserted == 0

    assert (
        db_session.query(Country).filter(Country.tenant_id == tenant.id).count()
        == len(DEFAULT_COUNTRIES)
    )
    assert (
        db_session.query(University).filter(University.tenant_id == tenant.id).count()
        == len(DEFAULT_UNIVERSITIES)
    )
    assert (
        db_session.query(Program).filter(Program.tenant_id == tenant.id).count()
        == len(DEFAULT_PROGRAMS)
    )


def test_seed_skips_only_existing_countries(db_session) -> None:
    tenant = _create_tenant(db_session, slug="apex")
    from datetime import datetime, timezone

    existing = DEFAULT_COUNTRIES[0]
    now = datetime.now(timezone.utc)
    db_session.add(
        Country(
            tenant_id=tenant.id,
            name=existing.name,
            code=existing.code,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    result = seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    assert result.countries_inserted == len(DEFAULT_COUNTRIES) - 1
    assert (
        db_session.query(Country).filter(Country.tenant_id == tenant.id).count()
        == len(DEFAULT_COUNTRIES)
    )


def test_seed_skips_only_existing_universities(db_session) -> None:
    tenant = _create_tenant(db_session, slug="apex")
    seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    existing_universities = {
        university.name
        for university in db_session.query(University)
        .filter(University.tenant_id == tenant.id)
        .all()
    }
    to_remove = sorted(existing_universities)[:1]
    for name in to_remove:
        row = (
            db_session.query(University)
            .filter(University.tenant_id == tenant.id, University.name == name)
            .one()
        )
        # Detach dependents (programs) so the delete doesn't FK-fail.
        for program in (
            db_session.query(Program)
            .filter(Program.university_id == row.id)
            .all()
        ):
            db_session.delete(program)
        db_session.delete(row)
    db_session.commit()

    result = seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    assert result.universities_inserted == len(to_remove)
    assert (
        db_session.query(University).filter(University.tenant_id == tenant.id).count()
        == len(DEFAULT_UNIVERSITIES)
    )


def test_seed_skips_only_existing_programs(db_session) -> None:
    tenant = _create_tenant(db_session, slug="apex")
    seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    target = DEFAULT_PROGRAMS[0]
    target_row = (
        db_session.query(Program)
        .filter(
            Program.tenant_id == tenant.id,
            Program.name == target.name,
        )
        .all()
    )
    target_universities = {
        university.id
        for university in db_session.query(University)
        .filter(
            University.tenant_id == tenant.id,
            University.name == target.university_name,
        )
        .all()
    }
    # If the (university_name, name) pair happens to be duplicated in the
    # default catalog, the test is picking the first one — remove both rows
    # tied to the same university so the seeder has to re-insert exactly one.
    rows_to_delete = [
        row
        for row in target_row
        if row.university_id in target_universities
    ]
    assert len(rows_to_delete) == 1
    for row in rows_to_delete:
        db_session.delete(row)
    db_session.commit()

    result = seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    assert result.programs_inserted == 1
    assert (
        db_session.query(Program).filter(Program.tenant_id == tenant.id).count()
        == len(DEFAULT_PROGRAMS)
    )


def test_seed_idempotent_even_when_re_seeding_partially_overlapping_tenant(
    db_session,
) -> None:
    """A tenant with some (but not all) of the defaults still seeds the rest once."""
    tenant = _create_tenant(db_session, slug="apex")
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    db_session.add(
        Country(
            tenant_id=tenant.id,
            name=DEFAULT_COUNTRIES[0].name,
            code=DEFAULT_COUNTRIES[0].code,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    first = seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)
    second = seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    assert first.countries_inserted == len(DEFAULT_COUNTRIES) - 1
    assert second.countries_inserted == 0
    assert (
        db_session.query(Country).filter(Country.tenant_id == tenant.id).count()
        == len(DEFAULT_COUNTRIES)
    )


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_seed_does_not_leak_rows_across_tenants(db_session) -> None:
    tenant_a = _create_tenant(db_session, slug="apex")
    tenant_b = _create_tenant(db_session, slug="globalreach")

    seed_default_master_data_for_tenant(db_session, tenant_id=tenant_a.id)
    # Do not seed tenant_b yet: its counts must remain zero.
    assert (
        db_session.query(Country).filter(Country.tenant_id == tenant_b.id).count()
        == 0
    )
    assert (
        db_session.query(University).filter(University.tenant_id == tenant_b.id).count()
        == 0
    )
    assert (
        db_session.query(Program).filter(Program.tenant_id == tenant_b.id).count()
        == 0
    )

    seed_default_master_data_for_tenant(db_session, tenant_id=tenant_b.id)

    a_country_ids = {
        row.id
        for row in db_session.query(Country)
        .filter(Country.tenant_id == tenant_a.id)
        .all()
    }
    b_country_ids = {
        row.id
        for row in db_session.query(Country)
        .filter(Country.tenant_id == tenant_b.id)
        .all()
    }
    assert a_country_ids.isdisjoint(b_country_ids)

    a_universities = (
        db_session.query(University).filter(University.tenant_id == tenant_a.id).all()
    )
    b_universities = (
        db_session.query(University).filter(University.tenant_id == tenant_b.id).all()
    )
    assert a_universities and b_universities
    for university in a_universities:
        assert university.country_id in a_country_ids
    for university in b_universities:
        assert university.country_id in b_country_ids


# ---------------------------------------------------------------------------
# Integration with the public read endpoints
# ---------------------------------------------------------------------------


def test_seeded_defaults_serve_through_public_list_endpoints(
    client, db_session
) -> None:
    tenant = _create_tenant(db_session, slug="apex")
    seed_default_master_data_for_tenant(db_session, tenant_id=tenant.id)

    countries_response = client.get(f"/tenants/{tenant.slug}/countries")
    assert countries_response.status_code == 200
    country_payload = countries_response.json()
    assert {item["name"] for item in country_payload} == {
        country.name for country in DEFAULT_COUNTRIES
    }
    sample_country_id = country_payload[0]["id"]
    sample_country_name = country_payload[0]["name"]

    universities_response = client.get(
        f"/tenants/{tenant.slug}/universities?country_id={sample_country_id}"
    )
    assert universities_response.status_code == 200
    university_payload = universities_response.json()
    expected_universities_for_country = {
        university.name
        for university in DEFAULT_UNIVERSITIES
        if university.country_name == sample_country_name
    }
    assert {item["name"] for item in university_payload} == expected_universities_for_country

    sample_university_id = university_payload[0]["id"]
    programs_response = client.get(
        f"/tenants/{tenant.slug}/programs?university_id={sample_university_id}"
    )
    assert programs_response.status_code == 200
    program_payload = programs_response.json()
    sample_university_name = university_payload[0]["name"]
    expected_programs_for_university = {
        program.name
        for program in DEFAULT_PROGRAMS
        if program.university_name == sample_university_name
    }
    assert {item["name"] for item in program_payload} == expected_programs_for_university


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_seed_rejects_non_positive_tenant_id(db_session) -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        seed_default_master_data_for_tenant(db_session, tenant_id=0)
    with pytest.raises(ValueError, match="tenant_id"):
        seed_default_master_data_for_tenant(db_session, tenant_id=-1)
    with pytest.raises(ValueError, match="tenant_id"):
        seed_default_master_data_for_tenant(db_session, tenant_id="not-an-int")  # type: ignore[arg-type]