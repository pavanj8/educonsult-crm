/** Marketing landing page path (E53; Requirements §10). */
export const LANDING_PATH = '/landing'

/** Public auth route paths. */

export const REGISTER_PATH = '/register'

/** Password-reset request page (E6; Journey J45). */
export const FORGOT_PASSWORD_PATH = '/forgot-password'

/** Password-reset confirmation page (E6; Journey J45). */
export const RESET_PASSWORD_PATH = '/reset-password'

/** Student dashboard route (E18; Journey J11). */
export const STUDENT_DASHBOARD_PATH = '/dashboard'

/** Document verifier dashboard route (E28; Journey J21). */
export const VERIFIER_DASHBOARD_PATH = '/verifier'

/** Visa processor dashboard route (E33; Journey J26; frontend #192). */
export const VISA_DASHBOARD_PATH = '/visa'

/** Counselor dashboard / assigned-application queue route (E21; Journey J14). */
export const COUNSELOR_DASHBOARD_PATH = '/my-applications'

/** Receptionist walk-in student intake form (E17; Journey J10). */
export const RECEPTIONIST_INTAKE_PATH = '/receptionist/intake'

/** Master-data admin UI (E14; Journey J7). */
export const MASTER_DATA_ADMIN_PATH = '/master-data'

/** Checklist template builder UI (E15; Journey J8). */
export const CHECKLIST_TEMPLATES_PATH = '/checklist-templates'

/**
 * Tenant branding settings route (E10; Journey J3; frontend ticket #112).
 * Consultancy owners edit their tenant's logo, brand color, and display
 * currency here; the route is guarded to that role.
 */
export const TENANT_BRANDING_PATH = '/branding'

/** Owner cross-branch comparison dashboard route (E42; Journey J35). */
export const OWNER_DASHBOARD_PATH = '/owner/dashboard'

/** Branch manager analytics dashboard (E41; Journey J34). */
export const BRANCH_MANAGER_DASHBOARD_PATH = '/analytics'

/** Super admin platform-wide stats dashboard (E43; Journey J36). */
export const SUPER_ADMIN_DASHBOARD_PATH = '/admin/analytics'

/** Plan and usage page for Consultancy Owners (E45; Journey J38). */
export const PLAN_AND_USAGE_PATH = '/plan-usage'

/** Super admin billing status overview (E47; Journey J40). */
export const BILLING_STATUS_PATH = '/admin/billing-status'
