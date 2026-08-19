import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../store/authStore'

export const LOGIN_PATH = '/login'

export default function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite">
        Loading…
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to={LOGIN_PATH} state={{ from: location }} replace />
  }

  return <Outlet />
}
