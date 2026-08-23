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

/** Counselor dashboard / assigned-application queue route (E21; Journey J14). */
export const COUNSELOR_DASHBOARD_PATH = '/my-applications'

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
