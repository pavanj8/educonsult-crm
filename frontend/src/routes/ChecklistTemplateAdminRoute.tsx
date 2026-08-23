/** Route guard for the checklist template builder UI (E15; Journey J8).

Mirrors the master-data admin guard: ``consultancy_owner`` and
``branch_manager`` both carry ``checklist_template:manage`` (see
``backend/app/rbac/permissions.py``), and both roles are the intended
operators for the per-stage/program document checklist maintenance UI
per the journey spec.
*/

import { Outlet } from 'react-router-dom'

import { useAuth } from '../store/authStore'

const CHECKLIST_TEMPLATE_ADMIN_ROLES = new Set([
  'consultancy_owner',
  'branch_manager',
])

export default function ChecklistTemplateAdminRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div
        className="auth-loading"
        role="status"
        aria-live="polite"
        aria-label="Loading"
      >
        Loading…
      </div>
    )
  }

  if (!user?.role || !CHECKLIST_TEMPLATE_ADMIN_ROLES.has(user.role)) {
    return (
      <div className="access-denied" data-testid="access-denied">
        <h2>Access denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    )
  }

  return <Outlet />
}
