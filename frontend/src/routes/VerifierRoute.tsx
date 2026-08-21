import { Outlet } from 'react-router-dom'

import { useAuth } from '../store/authStore'

const VERIFIER_ROLES = new Set(['document_verifier'])

/**
 * Role guard for the document verifier dashboard (E28; Journey J21): only
 * ``document_verifier`` users may reach the pending-document queue. Mirrors the
 * existing StaffManagerRoute / StudentRoute guard pattern.
 */
export default function VerifierRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite" aria-label="Loading">
        Loading…
      </div>
    )
  }

  if (!user?.role || !VERIFIER_ROLES.has(user.role)) {
    return (
      <div className="access-denied" data-testid="access-denied">
        <h2>Access denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    )
  }

  return <Outlet />
}
