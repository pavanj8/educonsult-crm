import { Outlet } from 'react-router-dom'

import { useAuth } from '../store/authStore'

const RECEPTIONIST_ROLES = new Set(['receptionist'])

/**
 * Role guard for the receptionist intake form (E17; Journey J10):
 * only ``receptionist`` users may reach the walk-in student intake
 * page. Mirrors the existing VerifierRoute / StaffManagerRoute
 * guard pattern.
 */
export default function ReceptionistRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite" aria-label="Loading">
        Loading…
      </div>
    )
  }

  if (!user?.role || !RECEPTIONIST_ROLES.has(user.role)) {
    return (
      <div className="access-denied" data-testid="access-denied">
        <h2>Access denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    )
  }

  return <Outlet />
}