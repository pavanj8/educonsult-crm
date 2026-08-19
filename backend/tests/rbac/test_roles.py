import pytest

from app.rbac import Role


def test_all_eight_roles_defined():
    assert len(Role) == 8


@pytest.mark.parametrize(
    ("role", "value"),
    [
        (Role.SUPER_ADMIN, "super_admin"),
        (Role.CONSULTANCY_OWNER, "consultancy_owner"),
        (Role.BRANCH_MANAGER, "branch_manager"),
        (Role.COUNSELOR, "counselor"),
        (Role.DOCUMENT_VERIFIER, "document_verifier"),
        (Role.VISA_PROCESSOR, "visa_processor"),
        (Role.RECEPTIONIST, "receptionist"),
        (Role.STUDENT, "student"),
    ],
)
def test_role_string_values(role, value):
    assert role == value
    assert role.value == value


def test_role_is_constructible_from_string():
    assert Role("counselor") is Role.COUNSELOR
