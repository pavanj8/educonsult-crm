/** Route guard for the master-data admin UI (E14; Journey J7).

 * Mirrors the staff-page guard: ``consultancy_owner`` and
 * ``branch_manager`` both carry ``master_data:manage`` (see
 * ``backend/app/rbac/permissions.py``), and both roles are the
 * intended operators for the master-data maintenance UI per the
 * journey spec.
 */

import { Outlet } from 'react-router-dom'

import { useAuth } from '../store/authStore'

const MASTER_DATA_ADMIN_ROLES = new Set(['consultancy_owner', 'branch_manager'])

export default function MasterDataAdminRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite" aria-label="Loading">
        Loading…
      </div>
    )
  }

  if (!user?.role || !MASTER_DATA_ADMIN_ROLES.has(user.role)) {
    return (
      <div className="access-denied" data-testid="access-denied">
        <h2>Access denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    )
  }

  return <Outlet />
}