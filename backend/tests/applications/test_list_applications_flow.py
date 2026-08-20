"""End-to-end student application list flow (E18, Journey J11, issue #146)."""

from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from tests.auth.test_register_student import VALID_PASSWORD, make_register_student_payload
from tests.branches.helpers import seed_branch
from tests.master_data.helpers import seed_master_data_chain


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_student_create_then_list_applications_flow(client, db_session):
    """Student creates multiple applications and lists them with independent stages."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain_one = seed_master_data_chain(db_session, tenant_id=tenant.id)
    chain_two = seed_master_data_chain(db_session, tenant_id=tenant.id)

    register_response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug=tenant.slug,
            branch_id=branch.id,
            email="list.flow@example.test",
        ),
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": "list.flow@example.test", "password": VALID_PASSWORD},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    first = client.post(
        "/applications",
        json={"university_id": chain_one[1].id, "program_id": chain_one[2].id},
        headers=headers,
    )
    assert first.status_code == 201
    first_body = first.json()

    second = client.post(
        "/applications",
        json={"university_id": chain_two[1].id, "program_id": chain_two[2].id},
        headers=headers,
    )
    assert second.status_code == 201
    second_body = second.json()
    assert second_body["id"] != first_body["id"]
    assert second_body["student_id"] == first_body["student_id"]

    list_response = client.get("/applications", headers=headers)
    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) == 2
    assert body[0]["id"] == first_body["id"]
    assert body[1]["id"] == second_body["id"]
    assert body[0]["university_id"] == chain_one[1].id
    assert body[1]["university_id"] == chain_two[1].id
    assert body[0]["stage"] == PipelineStage.REGISTERED.value
    assert body[1]["stage"] == PipelineStage.REGISTERED.value