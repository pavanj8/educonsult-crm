"""Register-student master-data validation tests (E16/E14; issue #139)."""

from app.models.tenant import Tenant
from tests.auth.test_register_student import VALID_PASSWORD, make_register_student_payload
from tests.branches.helpers import seed_branch
from tests.master_data.helpers import seed_master_data_chain


def _create_tenant(db_session, *, slug: str = "apex") -> Tenant:
    tenant = Tenant(name="Apex EduConsult", slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_register_student_rejects_unknown_country_id(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            target_country_id=999999999,
            target_university_id=None,
            target_program_id=None,
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid target country"


def test_register_student_rejects_unknown_university_id(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    country, _, _ = seed_master_data_chain(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            target_country_id=country.id,
            target_university_id=999999999,
            target_program_id=None,
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid target university"


def test_register_student_rejects_unknown_program_id(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    country, university, _ = seed_master_data_chain(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            target_country_id=country.id,
            target_university_id=university.id,
            target_program_id=999999999,
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid target program"


def test_register_student_persists_valid_master_data_ids(client, db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    country, university, program = seed_master_data_chain(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="valid.targets@example.test",
            target_country_id=country.id,
            target_university_id=university.id,
            target_program_id=program.id,
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["target_country_id"] == country.id
    assert body["target_university_id"] == university.id
    assert body["target_program_id"] == program.id
