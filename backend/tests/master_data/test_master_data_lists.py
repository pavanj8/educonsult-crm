"""Public master-data list endpoint tests (E14/E16; issue #139)."""

from app.models.tenant import Tenant
from tests.master_data.helpers import seed_country, seed_master_data_chain, seed_program, seed_university


def _create_tenant(db_session, *, slug: str = "apex") -> Tenant:
    tenant = Tenant(name="Apex EduConsult", slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_list_countries_returns_tenant_scoped_options(client, db_session):
    tenant = _create_tenant(db_session)
    canada = seed_country(db_session, tenant_id=tenant.id, name="Canada", code="CA")
    seed_country(db_session, tenant_id=tenant.id, name="United Kingdom", code="GB")

    response = client.get(f"/tenants/{tenant.slug}/countries")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] == canada.id
    assert body[0]["tenant_id"] == tenant.id
    assert body[0]["name"] == "Canada"
    assert body[0]["code"] == "CA"


def test_list_countries_requires_no_auth(client, db_session):
    tenant = _create_tenant(db_session)
    seed_country(db_session, tenant_id=tenant.id)

    response = client.get(f"/tenants/{tenant.slug}/countries")

    assert response.status_code == 200


def test_list_countries_unknown_tenant_returns_404(client):
    response = client.get("/tenants/missing/countries")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


def test_list_universities_filters_by_country(client, db_session):
    tenant = _create_tenant(db_session)
    canada = seed_country(db_session, tenant_id=tenant.id, name="Canada", code="CA")
    uk = seed_country(db_session, tenant_id=tenant.id, name="United Kingdom", code="GB")
    uoft = seed_university(
        db_session,
        tenant_id=tenant.id,
        country_id=canada.id,
        name="University of Toronto",
    )
    seed_university(
        db_session,
        tenant_id=tenant.id,
        country_id=uk.id,
        name="University of Manchester",
    )

    response = client.get(f"/tenants/{tenant.slug}/universities?country_id={canada.id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == uoft.id
    assert body[0]["country_id"] == canada.id
    assert body[0]["name"] == "University of Toronto"


def test_list_universities_unknown_country_returns_empty_list(client, db_session):
    tenant = _create_tenant(db_session)

    response = client.get(f"/tenants/{tenant.slug}/universities?country_id=999999999")

    assert response.status_code == 200
    assert response.json() == []


def test_list_programs_filters_by_university(client, db_session):
    tenant = _create_tenant(db_session)
    country, university, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
    seed_program(
        db_session,
        tenant_id=tenant.id,
        university_id=university.id,
        name="Business Administration MBA",
    )

    response = client.get(f"/tenants/{tenant.slug}/programs?university_id={university.id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {item["name"] for item in body} == {
        "Computer Science MSc",
        "Business Administration MBA",
    }
    assert all(item["university_id"] == university.id for item in body)
    assert program.id in {item["id"] for item in body}


def test_list_programs_unknown_university_returns_empty_list(client, db_session):
    tenant = _create_tenant(db_session)

    response = client.get(f"/tenants/{tenant.slug}/programs?university_id=999999999")

    assert response.status_code == 200
    assert response.json() == []


def test_master_data_routes_appear_in_openapi(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/tenants/{slug}/countries" in paths
    assert "/tenants/{slug}/universities" in paths
    assert "/tenants/{slug}/programs" in paths
