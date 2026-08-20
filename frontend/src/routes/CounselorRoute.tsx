import { Outlet } from 'react-router-dom'

import { useAuth } from '../store/authStore'

const COUNSELOR_ROLES = new Set(['counselor', 'branch_manager', 'consultancy_owner'])

export default function CounselorRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite" aria-label="Loading">
        Loading…
      </div>
    )
  }

  if (!user?.role || !COUNSELOR_ROLES.has(user.role)) {
    return (
      <div className="access-denied" data-testid="access-denied">
        <h2>Access denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    )
  }

  return <Outlet />
}
