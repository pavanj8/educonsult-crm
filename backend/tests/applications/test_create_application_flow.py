"""End-to-end student application creation flow (E18, Journey J11, issue #145)."""

from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from tests.auth.test_register_student import VALID_PASSWORD, make_register_student_payload
from tests.branches.helpers import seed_branch


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_student_register_login_create_application_flow(client, db_session):
    """Student registers, signs in with JWT, and creates university/program applications."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    register_response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug=tenant.slug,
            branch_id=branch.id,
            email="flow.student@example.test",
        ),
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": "flow.student@example.test", "password": VALID_PASSWORD},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    first = client.post(
        "/applications",
        json={"university_id": 101, "program_id": 201},
        headers=headers,
    )
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["university_id"] == 101
    assert first_body["program_id"] == 201
    assert first_body["stage"] == PipelineStage.REGISTERED.value
    assert first_body["tenant_id"] == tenant.id

    second = client.post(
        "/applications",
        json={"university_id": 102, "program_id": 202},
        headers=headers,
    )
    assert second.status_code == 201
    second_body = second.json()
    assert second_body["id"] != first_body["id"]
    assert second_body["student_id"] == first_body["student_id"]
    assert second_body["university_id"] == 102
