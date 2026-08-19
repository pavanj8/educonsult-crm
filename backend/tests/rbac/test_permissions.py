import pytest

from app.rbac import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    get_permissions_for_role,
    role_has_permission,
)


def test_every_role_has_permissions_defined():
    for role in Role:
        assert role in ROLE_PERMISSIONS
        assert len(get_permissions_for_role(role)) > 0


def test_super_admin_has_platform_permissions():
    perms = get_permissions_for_role(Role.SUPER_ADMIN)
    assert Permission.TENANT_CREATE in perms
    assert Permission.TENANT_READ in perms
    assert Permission.BILLING_PLATFORM in perms
    assert Permission.ANALYTICS_PLATFORM in perms
    assert Permission.BRANCH_CREATE not in perms


def test_consultancy_owner_has_tenant_wide_staff_and_branch_permissions():
    perms = get_permissions_for_role(Role.CONSULTANCY_OWNER)
    assert Permission.BRANCH_CREATE in perms
    assert Permission.STAFF_CREATE in perms
    assert Permission.ANALYTICS_TENANT in perms
    assert Permission.BILLING_MANAGE in perms
    assert Permission.TENANT_CREATE not in perms


def test_branch_manager_limited_to_branch_operations():
    perms = get_permissions_for_role(Role.BRANCH_MANAGER)
    assert Permission.STAFF_CREATE in perms
    assert Permission.ANALYTICS_BRANCH in perms
    assert Permission.BRANCH_CREATE not in perms
    assert Permission.ANALYTICS_TENANT not in perms


def test_counselor_has_assigned_student_and_counseling_permissions():
    perms = get_permissions_for_role(Role.COUNSELOR)
    assert Permission.STUDENT_READ_ASSIGNED in perms
    assert Permission.APPLICATION_READ_ASSIGNED in perms
    assert Permission.APPLICATION_ADVANCE_STAGE in perms
    assert Permission.MEETING_SCHEDULE in perms
    assert Permission.STUDENT_CREATE not in perms


def test_document_verifier_can_verify_documents_only():
    perms = get_permissions_for_role(Role.DOCUMENT_VERIFIER)
    assert Permission.DOCUMENT_VERIFY in perms
    assert Permission.DOCUMENT_READ in perms
    assert Permission.APPLICATION_ADVANCE_STAGE not in perms


def test_visa_processor_has_visa_permissions():
    perms = get_permissions_for_role(Role.VISA_PROCESSOR)
    assert Permission.VISA_MANAGE in perms
    assert Permission.APPLICATION_READ in perms
    assert Permission.DOCUMENT_VERIFY not in perms


def test_receptionist_is_intake_only():
    """ADR-0004: receptionist can register students but not verify docs or advance stages."""
    perms = get_permissions_for_role(Role.RECEPTIONIST)
    assert Permission.STUDENT_CREATE in perms
    assert Permission.APPLICATION_REASSIGN_COUNSELOR in perms
    assert Permission.DOCUMENT_VERIFY not in perms
    assert Permission.APPLICATION_ADVANCE_STAGE not in perms
    assert Permission.APPLICATION_MARK_TERMINAL not in perms


def test_student_has_self_service_permissions():
    perms = get_permissions_for_role(Role.STUDENT)
    assert Permission.STUDENT_READ_OWN in perms
    assert Permission.APPLICATION_CREATE in perms
    assert Permission.APPLICATION_READ_OWN in perms
    assert Permission.DOCUMENT_UPLOAD in perms
    assert Permission.STUDENT_CREATE not in perms


@pytest.mark.parametrize(
    ("role", "permission", "expected"),
    [
        (Role.COUNSELOR, Permission.MEETING_SCHEDULE, True),
        (Role.RECEPTIONIST, Permission.MEETING_SCHEDULE, False),
        (Role.STUDENT, Permission.LOAN_READ, True),
        (Role.STUDENT, Permission.LOAN_UPDATE, False),
    ],
)
def test_role_has_permission(role, permission, expected):
    assert role_has_permission(role, permission) is expected
