import { Outlet } from 'react-router-dom'

import { useAuth } from '../store/authStore'

const COUNSELOR_QUEUE_ROLES = new Set(['counselor', 'branch_manager', 'consultancy_owner'])

/**
 * Role guard for the counselor dashboard / assigned-application queue (E21;
 * Journey J14): the roles that hold ``application:read_assigned`` (counselor,
 * branch manager, consultancy owner). Mirrors the existing guard pattern.
 */
export default function CounselorRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite" aria-label="Loading">
        Loading…
      </div>
    )
  }

  if (!user?.role || !COUNSELOR_QUEUE_ROLES.has(user.role)) {
    return (
      <div className="access-denied" data-testid="access-denied">
        <h2>Access denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    )
  }

  return <Outlet />
}
