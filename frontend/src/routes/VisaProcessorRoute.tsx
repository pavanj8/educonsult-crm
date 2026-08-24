import { Outlet } from 'react-router-dom'

import { useAuth } from '../store/authStore'

const VISA_PROCESSOR_ROLES = new Set(['visa_processor'])

/**
 * Role guard for the visa processor dashboard (E33; Journey J26; #192):
 * only ``visa_processor`` users may reach the visa-stage applications
 * queue. Mirrors the existing :component:`VerifierRoute` /
 * :component:`CounselorRoute` guard pattern.
 */
export default function VisaProcessorRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite" aria-label="Loading">
        Loading…
      </div>
    )
  }

  if (!user?.role || !VISA_PROCESSOR_ROLES.has(user.role)) {
    return (
      <div className="access-denied" data-testid="access-denied">
        <h2>Access denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    )
  }

  return <Outlet />
}
