import pytest

from app.rbac.hierarchy import (
    RoleHierarchyError,
    assert_can_act_on_user,
    can_act_on_role,
    can_act_on_user,
    get_role_rank,
)
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser

_STAFF_SUBORDINATE_ROLES = [
    Role.BRANCH_MANAGER,
    Role.COUNSELOR,
    Role.DOCUMENT_VERIFIER,
    Role.VISA_PROCESSOR,
    Role.RECEPTIONIST,
]

_OPERATIONAL_ROLES = [
    Role.COUNSELOR,
    Role.DOCUMENT_VERIFIER,
    Role.VISA_PROCESSOR,
    Role.RECEPTIONIST,
]


def test_role_ranks_follow_requirements_hierarchy() -> None:
    assert get_role_rank(Role.SUPER_ADMIN) > get_role_rank(Role.CONSULTANCY_OWNER)
    assert get_role_rank(Role.CONSULTANCY_OWNER) > get_role_rank(Role.BRANCH_MANAGER)
    assert get_role_rank(Role.BRANCH_MANAGER) > get_role_rank(Role.COUNSELOR)
    assert get_role_rank(Role.COUNSELOR) == get_role_rank(Role.RECEPTIONIST)
    assert get_role_rank(Role.STUDENT) < get_role_rank(Role.RECEPTIONIST)


@pytest.mark.parametrize("target_role", _STAFF_SUBORDINATE_ROLES)
def test_consultancy_owner_can_act_on_tenant_staff_roles(target_role: Role) -> None:
    assert can_act_on_role(Role.CONSULTANCY_OWNER, target_role) is True


def test_consultancy_owner_cannot_act_on_owner_or_super_admin() -> None:
    assert can_act_on_role(Role.CONSULTANCY_OWNER, Role.CONSULTANCY_OWNER) is False
    assert can_act_on_role(Role.CONSULTANCY_OWNER, Role.SUPER_ADMIN) is False


@pytest.mark.parametrize("target_role", _OPERATIONAL_ROLES)
def test_branch_manager_can_act_on_operational_staff(target_role: Role) -> None:
    assert can_act_on_role(Role.BRANCH_MANAGER, target_role) is True


def test_branch_manager_cannot_act_on_owner_or_peer_manager() -> None:
    assert can_act_on_role(Role.BRANCH_MANAGER, Role.CONSULTANCY_OWNER) is False
    assert can_act_on_role(Role.BRANCH_MANAGER, Role.BRANCH_MANAGER) is False


@pytest.mark.parametrize(
    "actor_role",
    [
        Role.COUNSELOR,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
        Role.STUDENT,
    ],
)
@pytest.mark.parametrize("target_role", list(Role))
def test_non_management_roles_cannot_act_on_anyone(
    actor_role: Role, target_role: Role
) -> None:
    assert can_act_on_role(actor_role, target_role) is False


def test_operational_roles_are_peers() -> None:
    assert can_act_on_role(Role.COUNSELOR, Role.RECEPTIONIST) is False
    assert can_act_on_role(Role.DOCUMENT_VERIFIER, Role.VISA_PROCESSOR) is False


def test_super_admin_can_act_on_tenant_roles() -> None:
    assert can_act_on_role(Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER) is True
    assert can_act_on_role(Role.SUPER_ADMIN, Role.BRANCH_MANAGER) is True
    assert can_act_on_role(Role.SUPER_ADMIN, Role.COUNSELOR) is True


def test_super_admin_cannot_act_on_another_super_admin() -> None:
    assert can_act_on_role(Role.SUPER_ADMIN, Role.SUPER_ADMIN) is False


def test_only_super_admin_can_act_on_super_admin() -> None:
    assert can_act_on_role(Role.CONSULTANCY_OWNER, Role.SUPER_ADMIN) is False
    assert can_act_on_role(Role.SUPER_ADMIN, Role.SUPER_ADMIN) is False


def test_students_are_not_manageable_via_staff_hierarchy() -> None:
    for actor in [Role.CONSULTANCY_OWNER, Role.BRANCH_MANAGER, Role.SUPER_ADMIN]:
        assert can_act_on_role(actor, Role.STUDENT) is False


def test_owner_can_act_on_user_across_branches_in_same_tenant() -> None:
    actor = AuthenticatedUser(id=1, role=Role.CONSULTANCY_OWNER, tenant_id=10)
    assert (
        can_act_on_user(
            actor,
            target_role=Role.COUNSELOR,
            target_tenant_id=10,
            target_branch_id=99,
        )
        is True
    )


def test_owner_cannot_act_on_user_in_different_tenant() -> None:
    actor = AuthenticatedUser(id=2, role=Role.CONSULTANCY_OWNER, tenant_id=10)
    assert (
        can_act_on_user(
            actor,
            target_role=Role.COUNSELOR,
            target_tenant_id=20,
            target_branch_id=1,
        )
        is False
    )


def test_branch_manager_can_act_on_user_in_own_branch() -> None:
    actor = AuthenticatedUser(id=3, role=Role.BRANCH_MANAGER, tenant_id=10, branch_id=1)
    assert (
        can_act_on_user(
            actor,
            target_role=Role.COUNSELOR,
            target_tenant_id=10,
            target_branch_id=1,
        )
        is True
    )


def test_branch_manager_cannot_act_on_user_in_other_branch() -> None:
    actor = AuthenticatedUser(id=4, role=Role.BRANCH_MANAGER, tenant_id=10, branch_id=1)
    assert (
        can_act_on_user(
            actor,
            target_role=Role.COUNSELOR,
            target_tenant_id=10,
            target_branch_id=2,
        )
        is False
    )


def test_branch_manager_cannot_act_on_peer_branch_manager_even_in_same_branch() -> None:
    actor = AuthenticatedUser(id=5, role=Role.BRANCH_MANAGER, tenant_id=10, branch_id=1)
    assert (
        can_act_on_user(
            actor,
            target_role=Role.BRANCH_MANAGER,
            target_tenant_id=10,
            target_branch_id=1,
        )
        is False
    )


def test_super_admin_can_act_on_user_across_tenants() -> None:
    actor = AuthenticatedUser(id=6, role=Role.SUPER_ADMIN, tenant_id=None)
    assert (
        can_act_on_user(
            actor,
            target_role=Role.CONSULTANCY_OWNER,
            target_tenant_id=999,
            target_branch_id=None,
        )
        is True
    )


def test_counselor_cannot_act_on_user_even_in_same_branch() -> None:
    actor = AuthenticatedUser(id=7, role=Role.COUNSELOR, tenant_id=10, branch_id=1)
    assert (
        can_act_on_user(
            actor,
            target_role=Role.RECEPTIONIST,
            target_tenant_id=10,
            target_branch_id=1,
        )
        is False
    )


def test_assert_can_act_on_user_passes_for_valid_owner_action() -> None:
    actor = AuthenticatedUser(id=8, role=Role.CONSULTANCY_OWNER, tenant_id=10)
    assert_can_act_on_user(
        actor,
        target_role=Role.BRANCH_MANAGER,
        target_tenant_id=10,
        target_branch_id=3,
    )


def test_assert_can_act_on_user_raises_for_invalid_hierarchy() -> None:
    actor = AuthenticatedUser(id=9, role=Role.COUNSELOR, tenant_id=10, branch_id=1)
    with pytest.raises(RoleHierarchyError, match="cannot act on user"):
        assert_can_act_on_user(
            actor,
            target_role=Role.RECEPTIONIST,
            target_tenant_id=10,
            target_branch_id=1,
        )


def test_assert_can_act_on_user_raises_when_branch_manager_missing_branch_id() -> None:
    actor = AuthenticatedUser(id=10, role=Role.BRANCH_MANAGER, tenant_id=10, branch_id=None)
    with pytest.raises(RoleHierarchyError, match="requires branch_id"):
        assert_can_act_on_user(
            actor,
            target_role=Role.COUNSELOR,
            target_tenant_id=10,
            target_branch_id=1,
        )


def test_assert_can_act_on_user_raises_when_tenant_scoped_actor_missing_tenant_id() -> None:
    actor = AuthenticatedUser(id=11, role=Role.CONSULTANCY_OWNER, tenant_id=None)
    with pytest.raises(RoleHierarchyError, match="requires tenant_id"):
        assert_can_act_on_user(
            actor,
            target_role=Role.COUNSELOR,
            target_tenant_id=10,
            target_branch_id=1,
        )
