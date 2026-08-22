from enum import StrEnum
from functools import lru_cache

from app.rbac.roles import Role


class Permission(StrEnum):
    """Granular permissions derived from user journeys (docs/journeys.md)."""

    # Tenant management (J1, J2, J40)
    TENANT_CREATE = "tenant:create"
    TENANT_READ = "tenant:read"
    TENANT_UPDATE = "tenant:update"

    # Branch management (J4)
    BRANCH_CREATE = "branch:create"
    BRANCH_READ = "branch:read"
    BRANCH_UPDATE = "branch:update"

    # Staff management (J5, J6)
    STAFF_CREATE = "staff:create"
    STAFF_READ = "staff:read"
    STAFF_UPDATE = "staff:update"
    STAFF_DEACTIVATE = "staff:deactivate"

    # Master data & checklist templates (J7, J8)
    MASTER_DATA_MANAGE = "master_data:manage"
    CHECKLIST_TEMPLATE_MANAGE = "checklist_template:manage"

    # Students (J9, J10, J14)
    STUDENT_CREATE = "student:create"
    STUDENT_READ = "student:read"
    STUDENT_READ_ASSIGNED = "student:read_assigned"
    STUDENT_READ_OWN = "student:read_own"

    # Applications (J11–J13, J18, J31–J33)
    APPLICATION_CREATE = "application:create"
    APPLICATION_READ = "application:read"
    APPLICATION_READ_ASSIGNED = "application:read_assigned"
    APPLICATION_READ_OWN = "application:read_own"
    APPLICATION_ADVANCE_STAGE = "application:advance_stage"
    APPLICATION_MARK_TERMINAL = "application:mark_terminal"
    APPLICATION_REASSIGN_COUNSELOR = "application:reassign_counselor"

    # Documents (J19–J25)
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_READ = "document:read"
    DOCUMENT_VERIFY = "document:verify"

    # Counseling (J15–J17)
    MEETING_SCHEDULE = "meeting:schedule"
    MEETING_READ = "meeting:read"
    NOTE_CREATE = "note:create"
    NOTE_READ = "note:read"

    # Visa processing (J26–J28)
    VISA_MANAGE = "visa:manage"

    # Loan tracking (J29, J30)
    LOAN_READ = "loan:read"
    LOAN_UPDATE = "loan:update"

    # Analytics & reporting (J34–J37)
    ANALYTICS_BRANCH = "analytics:branch"
    ANALYTICS_TENANT = "analytics:tenant"
    ANALYTICS_PLATFORM = "analytics:platform"
    REPORT_EXPORT = "report:export"

    # Billing (J38–J40)
    BILLING_READ_OWN = "billing:read_own"
    BILLING_MANAGE = "billing:manage"
    BILLING_PLATFORM = "billing:platform"

    # Notifications (J43)
    NOTIFICATION_READ = "notification:read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.SUPER_ADMIN: frozenset(
        {
            Permission.TENANT_CREATE,
            Permission.TENANT_READ,
            Permission.TENANT_UPDATE,
            Permission.BILLING_PLATFORM,
            Permission.ANALYTICS_PLATFORM,
            Permission.NOTIFICATION_READ,
        }
    ),
    Role.CONSULTANCY_OWNER: frozenset(
        {
            Permission.TENANT_UPDATE,
            Permission.BRANCH_CREATE,
            Permission.BRANCH_READ,
            Permission.BRANCH_UPDATE,
            Permission.STAFF_CREATE,
            Permission.STAFF_READ,
            Permission.STAFF_UPDATE,
            Permission.STAFF_DEACTIVATE,
            Permission.MASTER_DATA_MANAGE,
            Permission.CHECKLIST_TEMPLATE_MANAGE,
            Permission.STUDENT_CREATE,
            Permission.STUDENT_READ,
            Permission.APPLICATION_READ,
            Permission.APPLICATION_READ_ASSIGNED,
            Permission.APPLICATION_ADVANCE_STAGE,
            Permission.APPLICATION_MARK_TERMINAL,
            Permission.APPLICATION_REASSIGN_COUNSELOR,
            Permission.DOCUMENT_READ,
            Permission.MEETING_SCHEDULE,
            Permission.MEETING_READ,
            Permission.NOTE_CREATE,
            Permission.NOTE_READ,
            Permission.VISA_MANAGE,
            Permission.LOAN_UPDATE,
            Permission.ANALYTICS_TENANT,
            Permission.REPORT_EXPORT,
            Permission.BILLING_READ_OWN,
            Permission.BILLING_MANAGE,
            Permission.NOTIFICATION_READ,
        }
    ),
    Role.BRANCH_MANAGER: frozenset(
        {
            Permission.STAFF_CREATE,
            Permission.STAFF_READ,
            Permission.STAFF_UPDATE,
            Permission.STAFF_DEACTIVATE,
            Permission.MASTER_DATA_MANAGE,
            Permission.CHECKLIST_TEMPLATE_MANAGE,
            Permission.STUDENT_CREATE,
            Permission.STUDENT_READ,
            Permission.APPLICATION_READ,
            Permission.APPLICATION_READ_ASSIGNED,
            Permission.APPLICATION_ADVANCE_STAGE,
            Permission.APPLICATION_MARK_TERMINAL,
            Permission.APPLICATION_REASSIGN_COUNSELOR,
            Permission.DOCUMENT_READ,
            Permission.MEETING_SCHEDULE,
            Permission.MEETING_READ,
            Permission.NOTE_CREATE,
            Permission.NOTE_READ,
            Permission.LOAN_UPDATE,
            Permission.ANALYTICS_BRANCH,
            Permission.REPORT_EXPORT,
            Permission.NOTIFICATION_READ,
        }
    ),
    Role.COUNSELOR: frozenset(
        {
            Permission.STUDENT_READ_ASSIGNED,
            Permission.APPLICATION_READ_ASSIGNED,
            Permission.APPLICATION_ADVANCE_STAGE,
            Permission.DOCUMENT_READ,
            Permission.MEETING_SCHEDULE,
            Permission.MEETING_READ,
            Permission.NOTE_CREATE,
            Permission.NOTE_READ,
            Permission.NOTIFICATION_READ,
        }
    ),
    Role.DOCUMENT_VERIFIER: frozenset(
        {
            Permission.DOCUMENT_READ,
            Permission.DOCUMENT_VERIFY,
            Permission.NOTIFICATION_READ,
        }
    ),
    Role.VISA_PROCESSOR: frozenset(
        {
            Permission.APPLICATION_READ,
            Permission.VISA_MANAGE,
            Permission.NOTIFICATION_READ,
        }
    ),
    Role.RECEPTIONIST: frozenset(
        {
            Permission.STUDENT_CREATE,
            Permission.STUDENT_READ,
            Permission.APPLICATION_READ,
            Permission.APPLICATION_REASSIGN_COUNSELOR,
            Permission.NOTIFICATION_READ,
        }
    ),
    Role.STUDENT: frozenset(
        {
            Permission.STUDENT_READ_OWN,
            Permission.APPLICATION_CREATE,
            Permission.APPLICATION_READ_OWN,
            Permission.DOCUMENT_UPLOAD,
            Permission.DOCUMENT_READ,
            Permission.MEETING_READ,
            Permission.LOAN_READ,
            Permission.NOTIFICATION_READ,
        }
    ),
}


@lru_cache
def get_permissions_for_role(role: Role) -> frozenset[Permission]:
    """Return the fixed permission set for a role."""
    return ROLE_PERMISSIONS[role]


def role_has_permission(role: Role, permission: Permission) -> bool:
    """Check whether a role is granted a permission."""
    return permission in get_permissions_for_role(role)
