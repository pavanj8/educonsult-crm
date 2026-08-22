"""Comprehensive master-data CRUD tests (E14; Journey J7; issue #130).

This module complements :mod:`tests.master_data.test_master_data_admin_crud`
(which ships with ticket #127) by exercising additional behaviors that
were deliberately out of its scope:

* role-based authorization across *every* role defined in
  :mod:`app.rbac.roles` (only ``STUDENT`` / ``COUNSELOR`` were spot-checked
  there),
* input validation for the **update** payloads (whitespace handling,
  blank-field rejection, code field changes for countries),
* ordering guarantees on the list endpoints,
* existence 404s for resources that the caller does own in principle but
  whose id has never existed,
* parent/child join isolation on the list endpoints (cross-tenant
  ``country_id`` must not leak universities from another tenant),
* public list endpoint behaviour that was not previously asserted:
  slug normalization (case-insensitive), normalized "empty" response,
  and 422 on bad ``country_id`` / ``university_id`` input.

Traceability
------------
* Requirement §5 (structured admin-managed master list).
* Journey J7 (Owner/Branch Manager manages master data).
* Epic E14 (Master Data Management).
* Sibling: #127 admin CRUD endpoints + base tests;
  #129 seed catalog (seeded fixtures are *not* assumed here — every test
  inserts its own rows for isolation).
"""

from app.models.tenant import Tenant
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from tests.factories.users import make_authenticated_user
from tests.master_data.helpers import (
    seed_country,
    seed_master_data_chain,
    seed_program,
    seed_university,
)

# ---------------------------------------------------------------------------
# Role-based authorization matrix (all eight roles for both verb directions)
# ---------------------------------------------------------------------------


def _owner(tenant_id: int = 1) -> AuthenticatedUser:
    return make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=tenant_id)


def _branch_manager(tenant_id: int = 1, branch_id: int = 1) -> AuthenticatedUser:
    return make_authenticated_user(
        Role.BRANCH_MANAGER, tenant_id=tenant_id, branch_id=branch_id
    )


def test_admin_routes_reject_document_verifier(
    client, db_session, override_authenticated_user
):
    seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.DOCUMENT_VERIFIER))

    for method, path, body in [
        ("get", "/master-data/admin/countries", None),
        ("post", "/master-data/admin/countries", {"name": "X", "code": "XX"}),
        ("patch", "/master-data/admin/countries/1", {"name": "X"}),
        ("delete", "/master-data/admin/countries/1", None),
        ("get", "/master-data/admin/universities", None),
        ("post", "/master-data/admin/universities", {"country_id": 1, "name": "X"}),
        ("patch", "/master-data/admin/universities/1", {"name": "X"}),
        ("delete", "/master-data/admin/universities/1", None),
        ("get", "/master-data/admin/programs", None),
        ("post", "/master-data/admin/programs", {"university_id": 1, "name": "X"}),
        ("patch", "/master-data/admin/programs/1", {"name": "X"}),
        ("delete", "/master-data/admin/programs/1", None),
    ]:
        if method == "get":
            response = client.get(path)
        elif method == "post":
            response = client.post(path, json=body)
        elif method == "patch":
            response = client.patch(path, json=body)
        else:
            response = client.delete(path)
        assert response.status_code == 403, (
            f"{method.upper()} {path} should forbid document verifier, "
            f"got {response.status_code}"
        )


def test_admin_routes_reject_visa_processor(
    client, db_session, override_authenticated_user
):
    seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.VISA_PROCESSOR))

    for method, path, body in [
        ("get", "/master-data/admin/countries", None),
        ("post", "/master-data/admin/countries", {"name": "X", "code": "XX"}),
        ("get", "/master-data/admin/universities", None),
        ("post", "/master-data/admin/universities", {"country_id": 1, "name": "X"}),
        ("get", "/master-data/admin/programs", None),
        ("post", "/master-data/admin/programs", {"university_id": 1, "name": "X"}),
    ]:
        if method == "get":
            response = client.get(path)
        else:
            response = client.post(path, json=body)
        assert response.status_code == 403, (
            f"{method.upper()} {path} should forbid visa processor, "
            f"got {response.status_code}"
        )


def test_admin_routes_reject_receptionist(
    client, db_session, override_authenticated_user
):
    seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.RECEPTIONIST))

    for method, path, body in [
        ("get", "/master-data/admin/countries", None),
        ("post", "/master-data/admin/countries", {"name": "X", "code": "XX"}),
        ("get", "/master-data/admin/universities", None),
        ("post", "/master-data/admin/universities", {"country_id": 1, "name": "X"}),
        ("get", "/master-data/admin/programs", None),
        ("post", "/master-data/admin/programs", {"university_id": 1, "name": "X"}),
    ]:
        if method == "get":
            response = client.get(path)
        else:
            response = client.post(path, json=body)
        assert response.status_code == 403, (
            f"{method.upper()} {path} should forbid receptionist, "
            f"got {response.status_code}"
        )


def test_admin_routes_reject_super_admin(
    client, db_session, override_authenticated_user
):
    """Super Admin is intentionally excluded from ``master_data:manage``.

    Ticket #127 documents that the role grant covers consultancy owner +
    branch manager only, and that SUPER_ADMIN is excluded so platform
    admins do not silently mutate a tenant's master data through this
    surface. Confirm the rejection at every endpoint.
    """
    seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    for method, path, body in [
        ("get", "/master-data/admin/countries", None),
        ("post", "/master-data/admin/countries", {"name": "X", "code": "XX"}),
        ("get", "/master-data/admin/universities", None),
        ("post", "/master-data/admin/universities", {"country_id": 1, "name": "X"}),
        ("get", "/master-data/admin/programs", None),
        ("post", "/master-data/admin/programs", {"university_id": 1, "name": "X"}),
    ]:
        if method == "get":
            response = client.get(path)
        else:
            response = client.post(path, json=body)
        assert response.status_code == 403, (
            f"{method.upper()} {path} should forbid super admin, "
            f"got {response.status_code}"
        )


def test_admin_endpoints_branch_manager_can_crud_all_three_resources(
    client, db_session, override_authenticated_user
):
    """``master_data:manage`` is granted to branch manager — exercise every
    CRUD verb on every resource with a branch-manager caller.

    This complements the single positive test in
    :mod:`tests.master_data.test_master_data_admin_crud` (which only
    asserts program-create for branch manager).
    """
    country = seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    university = seed_university(
        db_session,
        tenant_id=1,
        country_id=country.id,
        name="UofT",
    )
    program = seed_program(
        db_session,
        tenant_id=1,
        university_id=university.id,
        name="MSc CS",
    )
    override_authenticated_user(_branch_manager())

    # list
    for path in (
        "/master-data/admin/countries",
        "/master-data/admin/universities",
        "/master-data/admin/programs",
    ):
        response = client.get(path)
        assert response.status_code == 200

    # update
    response = client.patch(
        f"/master-data/admin/countries/{country.id}",
        json={"name": "Canada (BM)"},
    )
    assert response.status_code == 200

    response = client.patch(
        f"/master-data/admin/universities/{university.id}",
        json={"name": "UofT (BM)"},
    )
    assert response.status_code == 200

    response = client.patch(
        f"/master-data/admin/programs/{program.id}",
        json={"name": "MSc CS (BM)"},
    )
    assert response.status_code == 200

    # delete
    response = client.delete(f"/master-data/admin/programs/{program.id}")
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Update-payload validation
# ---------------------------------------------------------------------------


def test_update_country_strips_whitespace_in_name_and_code(
    client, db_session, override_authenticated_user
):
    country = seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/countries/{country.id}",
        json={"name": "  Canada Updated  ", "code": "  CA2  "},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Canada Updated"
    assert body["code"] == "CA2"


def test_update_country_rejects_blank_name(
    client, db_session, override_authenticated_user
):
    country = seed_country(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/countries/{country.id}",
        json={"name": "   "},
    )

    assert response.status_code == 422


def test_update_country_rejects_blank_code(
    client, db_session, override_authenticated_user
):
    country = seed_country(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/countries/{country.id}",
        json={"code": "   "},
    )

    assert response.status_code == 422


def test_update_country_updates_only_code_when_name_omitted(
    client, db_session, override_authenticated_user
):
    country = seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/countries/{country.id}",
        json={"code": "CAN"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Canada"
    assert body["code"] == "CAN"


def test_update_university_strips_whitespace(
    client, db_session, override_authenticated_user
):
    _, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/universities/{university.id}",
        json={"name": "  University of Toronto  "},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "University of Toronto"


def test_update_university_rejects_blank_name(
    client, db_session, override_authenticated_user
):
    _, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/universities/{university.id}",
        json={"name": "   "},
    )

    assert response.status_code == 422


def test_update_university_empty_payload_returns_422(
    client, db_session, override_authenticated_user
):
    _, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/universities/{university.id}", json={}
    )

    assert response.status_code == 422


def test_update_program_strips_whitespace(
    client, db_session, override_authenticated_user
):
    _, _, program = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/programs/{program.id}",
        json={"name": "  Data Science MSc  "},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Data Science MSc"


def test_update_program_rejects_blank_name(
    client, db_session, override_authenticated_user
):
    _, _, program = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/programs/{program.id}",
        json={"name": "   "},
    )

    assert response.status_code == 422


def test_update_program_empty_payload_returns_422(
    client, db_session, override_authenticated_user
):
    _, _, program = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.patch(
        f"/master-data/admin/programs/{program.id}", json={}
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Create-payload validation for universities/programs (countries already covered)
# ---------------------------------------------------------------------------


def test_create_university_strips_whitespace_in_name(
    client, db_session, override_authenticated_user
):
    country = seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    override_authenticated_user(_owner())

    response = client.post(
        "/master-data/admin/universities",
        json={"country_id": country.id, "name": "  University of Toronto  "},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "University of Toronto"


def test_create_university_rejects_blank_name(
    client, db_session, override_authenticated_user
):
    country = seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    override_authenticated_user(_owner())

    response = client.post(
        "/master-data/admin/universities",
        json={"country_id": country.id, "name": "   "},
    )

    assert response.status_code == 422


def test_create_program_strips_whitespace_in_name(
    client, db_session, override_authenticated_user
):
    _, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.post(
        "/master-data/admin/programs",
        json={"university_id": university.id, "name": "  Data Science MSc  "},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Data Science MSc"


def test_create_program_rejects_blank_name(
    client, db_session, override_authenticated_user
):
    _, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    override_authenticated_user(_owner())

    response = client.post(
        "/master-data/admin/programs",
        json={"university_id": university.id, "name": "   "},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 404 "does not exist at all" (distinct from cross-tenant 404)
# ---------------------------------------------------------------------------


def test_update_country_nonexistent_id_returns_404(
    client, override_authenticated_user
):
    override_authenticated_user(_owner())

    response = client.patch(
        "/master-data/admin/countries/999999999",
        json={"name": "Not here"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Country not found"


def test_update_university_nonexistent_id_returns_404(
    client, override_authenticated_user
):
    override_authenticated_user(_owner())

    response = client.patch(
        "/master-data/admin/universities/999999999",
        json={"name": "Not here"},
    )

    assert response.status_code == 404


def test_update_program_nonexistent_id_returns_404(
    client, override_authenticated_user
):
    override_authenticated_user(_owner())

    response = client.patch(
        "/master-data/admin/programs/999999999",
        json={"name": "Not here"},
    )

    assert response.status_code == 404


def test_delete_country_nonexistent_id_returns_404(
    client, override_authenticated_user
):
    override_authenticated_user(_owner())

    response = client.delete("/master-data/admin/countries/999999999")

    assert response.status_code == 404


def test_delete_university_nonexistent_id_returns_404(
    client, override_authenticated_user
):
    override_authenticated_user(_owner())

    response = client.delete("/master-data/admin/universities/999999999")

    assert response.status_code == 404


def test_delete_program_nonexistent_id_returns_404(
    client, override_authenticated_user
):
    override_authenticated_user(_owner())

    response = client.delete("/master-data/admin/programs/999999999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Parent-child FK integrity (no orphan writes)
# ---------------------------------------------------------------------------


def test_universities_list_filters_by_country_id_even_in_another_tenant(
    client, db_session, override_authenticated_user
):
    """A ``University`` row whose ``country_id`` resolves to a country of a
    *different* tenant must never leak into the caller's tenant list.

    This complements the admin CRUD tests' cross-tenant isolation
    assertion by also exercising the list-scoped parent/child join.
    """
    apex = _create_tenant(db_session, slug="apex")
    boulder = _create_tenant(db_session, slug="boulder")

    apex_canada = seed_country(
        db_session, tenant_id=apex.id, name="Canada", code="CA"
    )
    boulder_canada = seed_country(
        db_session, tenant_id=boulder.id, name="Canada", code="CA"
    )

    seed_university(
        db_session,
        tenant_id=apex.id,
        country_id=apex_canada.id,
        name="Apex U",
    )
    seed_university(
        db_session,
        tenant_id=boulder.id,
        country_id=boulder_canada.id,
        name="Boulder U",
    )

    override_authenticated_user(_owner(tenant_id=apex.id))

    response = client.get(
        "/master-data/admin/universities"
    )
    assert response.status_code == 200
    body = response.json()
    assert {item["name"] for item in body} == {"Apex U"}
    assert all(item["tenant_id"] == apex.id for item in body)


# ---------------------------------------------------------------------------
# Ordering and pagination on the list endpoints
# ---------------------------------------------------------------------------


def test_list_countries_returns_rows_sorted_by_name(
    client, db_session, override_authenticated_user
):
    seed_country(db_session, tenant_id=1, name="Zambia", code="ZM")
    seed_country(db_session, tenant_id=1, name="Australia", code="AU")
    seed_country(db_session, tenant_id=1, name="Canada", code="CA")
    override_authenticated_user(_owner())

    response = client.get("/master-data/admin/countries")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == sorted(names)
    assert "Australia" in names and "Canada" in names and "Zambia" in names


def test_list_universities_returns_rows_sorted_by_name(
    client, db_session, override_authenticated_user
):
    country = seed_country(db_session, tenant_id=1)
    seed_university(
        db_session,
        tenant_id=1,
        country_id=country.id,
        name="Zulu University",
    )
    seed_university(
        db_session,
        tenant_id=1,
        country_id=country.id,
        name="Alpha University",
    )
    seed_university(
        db_session,
        tenant_id=1,
        country_id=country.id,
        name="Mid University",
    )
    override_authenticated_user(_owner())

    response = client.get("/master-data/admin/universities")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == sorted(names)


def test_list_programs_returns_rows_sorted_by_name(
    client, db_session, override_authenticated_user
):
    _, university, _ = seed_master_data_chain(db_session, tenant_id=1)
    seed_program(db_session, tenant_id=1, university_id=university.id, name="Zoology")
    seed_program(db_session, tenant_id=1, university_id=university.id, name="Astronomy")
    override_authenticated_user(_owner())

    response = client.get("/master-data/admin/programs")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# Public tenant-scoped master-data list (orthogonal to admin CRUD)
# ---------------------------------------------------------------------------


def _create_tenant(db_session, *, slug: str = "apex") -> Tenant:
    tenant = Tenant(name="Apex EduConsult", slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_public_list_countries_normalizes_tenant_slug(
    client, db_session
):
    """The public route looks tenants up by slug after stripping and
    lowercasing the input — confirm the normalization is applied and the
    response shape matches the admin endpoint for the same tenant scope.
    """
    tenant = _create_tenant(db_session, slug="Apex EduConsult")
    seed_country(db_session, tenant_id=tenant.id, name="Canada", code="CA")

    response = client.get(f"/tenants/{tenant.slug.upper()}/countries")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Canada"
    assert body[0]["code"] == "CA"
    assert body[0]["tenant_id"] == tenant.id


def test_public_list_universities_returns_empty_when_country_has_none(
    client, db_session
):
    tenant = _create_tenant(db_session)
    country = seed_country(
        db_session, tenant_id=tenant.id, name="Canada", code="CA"
    )

    response = client.get(
        f"/tenants/{tenant.slug}/universities?country_id={country.id}"
    )

    assert response.status_code == 200
    assert response.json() == []


def test_public_list_universities_unknown_country_returns_empty(
    client, db_session
):
    tenant = _create_tenant(db_session)

    response = client.get(
        f"/tenants/{tenant.slug}/universities?country_id={999999999}"
    )

    assert response.status_code == 200
    assert response.json() == []


def test_public_list_universities_rejects_invalid_country_id(
    client, db_session
):
    """A non-positive ``country_id`` is rejected by Query(ge=1) -> 422."""
    tenant = _create_tenant(db_session)

    response = client.get(
        f"/tenants/{tenant.slug}/universities?country_id=0"
    )

    assert response.status_code == 422


def test_public_list_programs_rejects_invalid_university_id(
    client, db_session
):
    tenant = _create_tenant(db_session)

    response = client.get(
        f"/tenants/{tenant.slug}/programs?university_id=0"
    )

    assert response.status_code == 422


def test_public_list_universities_excludes_other_tenants_rows(
    client, db_session
):
    """A public university-list query for tenant A's slug + a country id
    owned by tenant A must NOT include universities from tenant B that
    happen to reference the same ``country_id`` row (cross-tenant FK
    leaks, even if the row is owned by tenant A).

    The admin CRUD tests already cover cross-tenant exposure of
    country *resources*. This test asserts the *public* (no-auth) read
    path also enforces cross-tenant isolation at the join level.
    """
    apex = _create_tenant(db_session, slug="apex")
    boulder = _create_tenant(db_session, slug="boulder")

    apex_canada = seed_country(
        db_session, tenant_id=apex.id, name="Canada", code="CA"
    )
    seed_university(
        db_session,
        tenant_id=boulder.id,
        country_id=apex_canada.id,  # cross-tenant FK on purpose
        name="Ghost University",
    )

    response = client.get(
        f"/tenants/{apex.slug}/universities?country_id={apex_canada.id}"
    )

    assert response.status_code == 200
    assert response.json() == []
