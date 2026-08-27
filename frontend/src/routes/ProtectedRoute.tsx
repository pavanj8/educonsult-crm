import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../store/authStore'
import { LANDING_PATH } from './paths'

export const LOGIN_PATH = '/login'

export default function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite" aria-label="Loading">
        Loading…
      </div>
    )
  }

  if (!isAuthenticated) {
    // Someone typing the bare URL is a visitor, not a user who bounced off a
    // deep link: send them to the marketing page, which is where the "Log In"
    // call to action lives. Any other protected path still goes straight to
    // the login form, and carries `from` so they resume where they meant to be.
    const target = location.pathname === '/' ? LANDING_PATH : LOGIN_PATH
    return <Navigate to={target} state={{ from: location }} replace />
  }

  return <Outlet />
}
