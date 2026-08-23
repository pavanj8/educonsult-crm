"""Staff-created student record permission matrix (E17, Journey J10, issue #143).

Proves ``POST /students`` enforces the role, tenant, and branch scoping
required by Requirements §3 and ADR-0004:

* Roles granted ``STUDENT_CREATE`` (Consultancy Owner, Branch Manager,
  Receptionist) may create a student record.
* Branch-scoped roles (Branch Manager, Receptionist) may only create a
  student in their own branch.
* Tenant-scoped roles (every role except Super Admin) may not create a
  student in another tenant's branch (cross-tenant denial).
* Roles *not* granted ``STUDENT_CREATE`` are denied with HTTP 403.
* Unauthenticated callers are denied with HTTP 401.
"""

import pytest

from app.models.user import User
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


def _student_payload(branch_id: int, **overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": "walkin@example.test",
        "password": "Walkin-password-123",
        "name": "Walk In Student",
        "phone": "+91 9876543210",
        "date_of_birth": "2000-01-01",
        "branch_id": branch_id,
    }
    payload.update(overrides)
    return payload


# Roles granted ``STUDENT_CREATE`` (see ``ROLE_PERMISSIONS`` in
# ``app/rbac/permissions.py``).
_ROLES_WITH_STUDENT_CREATE = (Role.CONSULTANCY_OWNER, Role.BRANCH_MANAGER, Role.RECEPTIONIST)

# Roles explicitly *not* granted ``STUDENT_CREATE``; the endpoint must
# reject them with 403.
_ROLES_WITHOUT_STUDENT_CREATE = (
    Role.COUNSELOR,
    Role.DOCUMENT_VERIFIER,
    Role.VISA_PROCESSOR,
    Role.STUDENT,
    Role.SUPER_ADMIN,
)


def test_branch_manager_creates_student_in_own_branch(client, db_session, override_authenticated_user):
    branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, tenant_id=1, branch_id=branch.id)
    )

    response = client.post("/students", json=_student_payload(branch.id))

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "student"
    assert body["tenant_id"] == 1
    assert body["branch_id"] == branch.id
    created = db_session.get(User, body["id"])
    assert created is not None
    assert created.branch_id == branch.id
    assert created.tenant_id == 1


def test_branch_manager_cannot_create_student_in_other_branch(
    client, db_session, override_authenticated_user
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_branch = seed_branch(db_session, tenant_id=1, name="Other Branch", city="Delhi")
    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, tenant_id=1, branch_id=own_branch.id)
    )

    response = client.post("/students", json=_student_payload(other_branch.id))

    assert response.status_code == 403


def test_owner_can_create_student_in_any_branch_within_tenant(
    client, db_session, override_authenticated_user
):
    branch_one = seed_branch(db_session, tenant_id=1, name="Branch One", city="Mumbai")
    branch_two = seed_branch(db_session, tenant_id=1, name="Branch Two", city="Delhi")
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response_one = client.post(
        "/students",
        json=_student_payload(branch_one.id, email="owner.b1@example.test"),
    )
    response_two = client.post(
        "/students",
        json=_student_payload(
            branch_two.id,
            email="owner.b2@example.test",
        ),
    )

    assert response_one.status_code == 201
    assert response_one.json()["branch_id"] == branch_one.id
    assert response_one.json()["tenant_id"] == 1
    assert response_two.status_code == 201
    assert response_two.json()["branch_id"] == branch_two.id
    assert response_two.json()["tenant_id"] == 1


def test_owner_cannot_create_student_in_other_tenant_branch(
    client, db_session, override_authenticated_user
):
    other_tenant_branch = seed_branch(db_session, tenant_id=2, name="Other Tenant Branch", city="Pune")
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post("/students", json=_student_payload(other_tenant_branch.id))

    assert response.status_code == 404
    assert response.json()["detail"] == "Branch not found"


def test_receptionist_cannot_create_student_in_other_tenant_branch(
    client, db_session, override_authenticated_user
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_tenant_branch = seed_branch(
        db_session, tenant_id=2, name="Other Tenant Branch", city="Pune"
    )
    override_authenticated_user(
        make_authenticated_user(Role.RECEPTIONIST, tenant_id=1, branch_id=own_branch.id)
    )

    # Branch-scoped roles (receptionist) are denied at the branch-scope check
    # *before* the cross-tenant branch lookup runs, so the response is 403
    # rather than 404 — this is the correct security behavior (no leakage
    # of whether the branch exists in another tenant).
    response = client.post("/students", json=_student_payload(other_tenant_branch.id))

    assert response.status_code == 403


def test_branch_manager_cannot_create_student_in_other_tenant_branch(
    client, db_session, override_authenticated_user
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_tenant_branch = seed_branch(
        db_session, tenant_id=2, name="Other Tenant Branch", city="Pune"
    )
    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, tenant_id=1, branch_id=own_branch.id)
    )

    # Branch-scoped roles (branch manager) are denied at the branch-scope
    # check before the cross-tenant branch lookup, so the response is 403
    # rather than 404 — same reasoning as the receptionist case above.
    response = client.post("/students", json=_student_payload(other_tenant_branch.id))

    assert response.status_code == 403


def test_receptionist_cannot_create_student_for_nonexistent_branch(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    override_authenticated_user(
        make_authenticated_user(Role.RECEPTIONIST, tenant_id=1, branch_id=branch.id)
    )

    # A nonexistent branch is rejected at the branch-scope check (403)
    # before the existence check, so the response is 403, not 404.
    response = client.post("/students", json=_student_payload(branch_id=999_999))

    assert response.status_code == 403


def test_owner_cannot_create_student_for_nonexistent_branch(
    client, db_session, override_authenticated_user
):
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    # Tenant-scoped roles (owner, no branch_id) reach the existence check,
    # so a nonexistent branch returns 404 "Branch not found".
    response = client.post("/students", json=_student_payload(branch_id=999_999))

    assert response.status_code == 404
    assert response.json()["detail"] == "Branch not found"


@pytest.mark.parametrize("role", _ROLES_WITHOUT_STUDENT_CREATE)
def test_roles_without_student_create_permission_are_denied(
    client, db_session, override_authenticated_user, role: Role
):
    branch = seed_branch(db_session, tenant_id=1, name="Branch", city="Mumbai")
    override_authenticated_user(
        make_authenticated_user(role, tenant_id=1, branch_id=branch.id)
    )

    response = client.post("/students", json=_student_payload(branch.id))

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_unauthenticated_request_is_denied(client, db_session):
    branch = seed_branch(db_session, tenant_id=1, name="Branch", city="Mumbai")

    response = client.post("/students", json=_student_payload(branch.id))

    assert response.status_code == 401