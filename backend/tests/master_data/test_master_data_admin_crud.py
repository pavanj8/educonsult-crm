"""Admin-scoped CRUD tests for master data (E14; Journey J7; issue #127).

Each section exercises the four CRUD verbs (list, create, update, delete)
for one of the three admin-scoped resources: countries, universities,
programs. The tests prove:

* ``master_data:manage`` permission is required (CONSULTANCY_OWNER and
  BRANCH_MANAGER are granted; other roles are denied with 403).
* Writes inherit ``tenant_id`` from the authenticated caller.
* Cross-tenant reads surface as 404 (never 403), so tenant ids cannot
  be enumerated by probing.
* Parent FKs (``country_id``, ``university_id``) must resolve to a
  row in the caller's tenant; cross-tenant FK values yield 422.

The tests use the existing ``seed_*`` helpers in
:mod:`tests.master_data.helpers` and the ``override_authenticated_user``
fixture from the shared conftest.
"""

from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user
from tests.master_data.helpers import (
    seed_country,
    seed_master_data_chain,
    seed_program,
    seed_university,
)


# ---------------------------------------------------------------------------
# Countries CRUD
# ---------------------------------------------------------------------------


def test_create_country_success_as_owner(client, override_authenticated_user):
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.post(
        "/master-data/admin/countries",
        json={"name": "Germany", "code": "DE"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["tenant_id"] == 1
    assert body["name"] == "Germany"
    assert body["code"] == "DE"


def test_create_country_strips_whitespace(client, override_authenticated_user):
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.post(
        "/master-data/admin/countries",
        json={"name": "  Germany  ", "code": "  DE  "},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Germany"
    assert response.json()["code"] == "DE"


def test_create_country_rejects_unauthenticated(client):
    response = client.post(
        "/master-data/admin/countries",
        json={"name": "Germany", "code": "DE"},
    )

    assert response.status_code == 401


def test_create_country_rejects_student(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.STUDENT))

    response = client.post(
        "/master-data/admin/countries",
        json={"name": "Germany", "code": "DE"},
    )

    assert response.status_code == 403


def test_create_country_rejects_counselor(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR))

    response = client.post(
        "/master-data/admin/countries",
        json={"name": "Germany", "code": "DE"},
    )

    assert response.status_code == 403


def test_create_country_rejects_blank_name(client, override_authenticated_user):
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.post(
        "/master-data/admin/countries",
        json={"name": "   ", "code": "DE"},
    )

    assert response.status_code == 422


def test_list_countries_returns_only_callers_tenant(
    client, db_session, override_authenticated_user
):
    seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    seed_country(db_session, tenant_id=2, name="Australia", code="AU")

    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, tenant_id=1, branch_id=1)
    )

    response = client.get("/master-data/admin/countries")

    assert response.status_code == 200
    body = response.json()
    assert {item["name"] for item in body} == {"Canada"}
    assert all(item["tenant_id"] == 1 for item in body)


def test_list_countries_empty_when_no_data(client, override_authenticated_user):
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.get("/master-data/admin/countries")

    assert response.status_code == 200
    assert response.json() == []


def test_update_country_success(client, db_session, override_authenticated_user):
    country = seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(
        f"/master-data/admin/countries/{country.id}",
        json={"name": "Canada Updated"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Canada Updated"
    assert response.json()["code"] == "CA"


def test_update_country_cross_tenant_returns_404(
    client, db_session, override_authenticated_user
):
    other = seed_country(db_session, tenant_id=99, name="Hidden", code="ZZ")
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(
        f"/master-data/admin/countries/{other.id}",
        json={"name": "Hijacked"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Country not found"


def test_update_country_empty_payload_returns_422(
    client, db_session, override_authenticated_user
):
    country = seed_country(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(f"/master-data/admin/countries/{country.id}", json={})

    assert response.status_code == 422


def test_update_country_rejects_counselor(
    client, db_session, override_authenticated_user
):
    country = seed_country(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR))

    response = client.patch(
        f"/master-data/admin/countries/{country.id}",
        json={"name": "Nope"},
    )

    assert response.status_code == 403


def test_delete_country_success(client, db_session, override_authenticated_user):
    country = seed_country(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.delete(f"/master-data/admin/countries/{country.id}")

    assert response.status_code == 204
    assert response.content == b""

    # Confirm the row is gone.
    list_response = client.get("/master-data/admin/countries")
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_delete_country_cross_tenant_returns_404(
    client, db_session, override_authenticated_user
):
    other = seed_country(db_session, tenant_id=99)
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.delete(f"/master-data/admin/countries/{other.id}")

    assert response.status_code == 404


def test_delete_country_branch_manager_without_branch_still_allowed(
    client, db_session, override_authenticated_user
):
    """Master data is tenant-scoped, not branch-scoped, so a branch manager
    whose ``branch_id`` is missing can still manage their tenant's rows
    (the ``master_data:manage`` grant is tenant-wide for both owner and
    branch manager)."""
    country = seed_country(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, tenant_id=1, branch_id=None)
    )

    response = client.delete(f"/master-data/admin/countries/{country.id}")

    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Universities CRUD
# ---------------------------------------------------------------------------


def test_create_university_success(client, db_session, override_authenticated_user):
    country = seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.post(
        "/master-data/admin/universities",
        json={"country_id": country.id, "name": "University of Toronto"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["tenant_id"] == 1
    assert body["country_id"] == country.id
    assert body["name"] == "University of Toronto"


def test_create_university_cross_tenant_country_returns_422(
    client, db_session, override_authenticated_user
):
    other_country = seed_country(db_session, tenant_id=99)
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.post(
        "/master-data/admin/universities",
        json={"country_id": other_country.id, "name": "Stealth University"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid country for the caller's tenant"


def test_create_university_missing_country_returns_422(
    client, override_authenticated_user
):
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.post(
        "/master-data/admin/universities",
        json={"country_id": 999999999, "name": "No country"},
    )

    assert response.status_code == 422


def test_create_university_rejects_student(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.STUDENT))

    response = client.post(
        "/master-data/admin/universities",
        json={"country_id": 1, "name": "X"},
    )

    assert response.status_code == 403


def test_list_universities_returns_only_callers_tenant(
    client, db_session, override_authenticated_user
):
    own_country = seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    other_country = seed_country(db_session, tenant_id=2, name="Australia", code="AU")
    seed_university(db_session, tenant_id=1, country_id=own_country.id, name="UofT")
    seed_university(
        db_session,
        tenant_id=2,
        country_id=other_country.id,
        name="UofMelbourne",
    )

    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, tenant_id=1, branch_id=1)
    )

    response = client.get("/master-data/admin/universities")

    assert response.status_code == 200
    body = response.json()
    assert {item["name"] for item in body} == {"UofT"}
    assert all(item["tenant_id"] == 1 for item in body)


def test_update_university_success(client, db_session, override_authenticated_user):
    country, university, _ = seed_master_data_chain(
        db_session, tenant_id=1
    )
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(
        f"/master-data/admin/universities/{university.id}",
        json={"name": "University of Toronto (Renamed)"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "University of Toronto (Renamed)"
    assert response.json()["country_id"] == country.id


def test_update_university_cross_tenant_country_returns_422(
    client, db_session, override_authenticated_user
):
    country, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    other_country = seed_country(db_session, tenant_id=99)
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(
        f"/master-data/admin/universities/{university.id}",
        json={"country_id": other_country.id},
    )

    assert response.status_code == 422


def test_update_university_cross_tenant_returns_404(
    client, db_session, override_authenticated_user
):
    other_country = seed_country(db_session, tenant_id=99)
    other_university = seed_university(
        db_session, tenant_id=99, country_id=other_country.id
    )
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(
        f"/master-data/admin/universities/{other_university.id}",
        json={"name": "Stolen"},
    )

    assert response.status_code == 404


def test_delete_university_success(client, db_session, override_authenticated_user):
    _, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.delete(f"/master-data/admin/universities/{university.id}")

    assert response.status_code == 204
    list_response = client.get("/master-data/admin/universities")
    assert list_response.json() == []


def test_delete_university_cross_tenant_returns_404(
    client, db_session, override_authenticated_user
):
    other_country = seed_country(db_session, tenant_id=99)
    other_university = seed_university(
        db_session, tenant_id=99, country_id=other_country.id
    )
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.delete(f"/master-data/admin/universities/{other_university.id}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Programs CRUD
# ---------------------------------------------------------------------------


def test_create_program_success(client, db_session, override_authenticated_user):
    _, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.post(
        "/master-data/admin/programs",
        json={"university_id": university.id, "name": "Data Science MSc"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["tenant_id"] == 1
    assert body["university_id"] == university.id
    assert body["name"] == "Data Science MSc"


def test_create_program_cross_tenant_university_returns_422(
    client, db_session, override_authenticated_user
):
    other_country = seed_country(db_session, tenant_id=99)
    other_university = seed_university(
        db_session, tenant_id=99, country_id=other_country.id
    )
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.post(
        "/master-data/admin/programs",
        json={"university_id": other_university.id, "name": "Foreign Program"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid university for the caller's tenant"


def test_create_program_allowed_for_branch_manager(
    client, db_session, override_authenticated_user
):
    """``master_data:manage`` is granted to both owner and branch manager."""
    _, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, tenant_id=1, branch_id=1)
    )

    response = client.post(
        "/master-data/admin/programs",
        json={"university_id": university.id, "name": "BM-created Program"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "BM-created Program"


def test_create_program_rejects_counselor(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR))

    response = client.post(
        "/master-data/admin/programs",
        json={"university_id": 1, "name": "X"},
    )

    assert response.status_code == 403


def test_list_programs_returns_only_callers_tenant(
    client, db_session, override_authenticated_user
):
    country, university, program = seed_master_data_chain(db_session, tenant_id=1)
    other_country = seed_country(db_session, tenant_id=2)
    other_university = seed_university(
        db_session, tenant_id=2, country_id=other_country.id
    )
    seed_program(db_session, tenant_id=2, university_id=other_university.id)

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.get("/master-data/admin/programs")

    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body} == {program.id}
    assert all(item["tenant_id"] == 1 for item in body)


def test_update_program_success(client, db_session, override_authenticated_user):
    _, university, program = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(
        f"/master-data/admin/programs/{program.id}",
        json={"name": "Computer Science (Renamed)"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Computer Science (Renamed)"
    assert response.json()["university_id"] == university.id


def test_update_program_cross_tenant_university_returns_422(
    client, db_session, override_authenticated_user
):
    _, _, program = seed_master_data_chain(db_session, tenant_id=1)
    other_country = seed_country(db_session, tenant_id=99)
    other_university = seed_university(
        db_session, tenant_id=99, country_id=other_country.id
    )
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(
        f"/master-data/admin/programs/{program.id}",
        json={"university_id": other_university.id},
    )

    assert response.status_code == 422


def test_update_program_cross_tenant_returns_404(
    client, db_session, override_authenticated_user
):
    other_country = seed_country(db_session, tenant_id=99)
    other_university = seed_university(
        db_session, tenant_id=99, country_id=other_country.id
    )
    other_program = seed_program(
        db_session, tenant_id=99, university_id=other_university.id
    )
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.patch(
        f"/master-data/admin/programs/{other_program.id}",
        json={"name": "Stolen"},
    )

    assert response.status_code == 404


def test_delete_program_success(client, db_session, override_authenticated_user):
    _, _, program = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.delete(f"/master-data/admin/programs/{program.id}")

    assert response.status_code == 204
    list_response = client.get("/master-data/admin/programs")
    assert list_response.json() == []


def test_delete_program_cross_tenant_returns_404(
    client, db_session, override_authenticated_user
):
    other_country = seed_country(db_session, tenant_id=99)
    other_university = seed_university(
        db_session, tenant_id=99, country_id=other_country.id
    )
    other_program = seed_program(
        db_session, tenant_id=99, university_id=other_university.id
    )
    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1)
    )

    response = client.delete(f"/master-data/admin/programs/{other_program.id}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# OpenAPI surface
# ---------------------------------------------------------------------------


def test_master_data_admin_routes_appear_in_openapi(client, override_authenticated_user):
    # Auth gate just to satisfy any startup-time checks.
    override_authenticated_user(make_authenticated_user(Role.STUDENT))

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    expected = {
        "/master-data/admin/countries": {"get", "post"},
        "/master-data/admin/countries/{country_id}": {"patch", "delete"},
        "/master-data/admin/universities": {"get", "post"},
        "/master-data/admin/universities/{university_id}": {"patch", "delete"},
        "/master-data/admin/programs": {"get", "post"},
        "/master-data/admin/programs/{program_id}": {"patch", "delete"},
    }
    for path, methods in expected.items():
        assert path in paths, f"missing path: {path}"
        assert methods.issubset(set(paths[path].keys())), (
            f"missing methods {methods - set(paths[path].keys())} on {path}"
        )
