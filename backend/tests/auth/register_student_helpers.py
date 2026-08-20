"""Shared helpers for POST /auth/register-student tests (E16; issue #140)."""

from app.models.tenant import Tenant

VALID_PASSWORD = "StudentPass1!"


def create_tenant(
    db_session,
    *,
    name: str = "Apex EduConsult",
    slug: str = "apex",
) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def make_register_student_payload(
    *,
    tenant_slug: str = "apex",
    branch_id: int = 1,
    email: str = "new.student@example.test",
    password: str = VALID_PASSWORD,
    name: str = "Rahul Kumar",
    phone: str = "+91-9876543210",
    date_of_birth: str = "2000-05-15",
    target_country_id: int | None = 10,
    target_university_id: int | None = 20,
    target_program_id: int | None = 30,
) -> dict:
    payload = {
        "tenant_slug": tenant_slug,
        "branch_id": branch_id,
        "email": email,
        "password": password,
        "name": name,
        "phone": phone,
        "date_of_birth": date_of_birth,
    }
    if target_country_id is not None:
        payload["target_country_id"] = target_country_id
    if target_university_id is not None:
        payload["target_university_id"] = target_university_id
    if target_program_id is not None:
        payload["target_program_id"] = target_program_id
    return payload
