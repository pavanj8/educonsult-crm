import { Link, Outlet } from 'react-router-dom'

import NotificationBell from '../components/notifications/NotificationBell'
import { useAuth } from '../store/authStore'

export default function AppLayout() {
  const { user } = useAuth()

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="app-header__brand">
          <h1>EduConsult CRM</h1>
          {user?.role === 'super_admin' ? (
            <nav className="app-header__nav" aria-label="Main">
              <Link to="/tenants" data-testid="nav-tenants">
                Tenants
              </Link>
            </nav>
          ) : null}
          {user?.role === 'consultancy_owner' ? (
            <nav className="app-header__nav" aria-label="Main">
              <Link to="/branches" data-testid="nav-branches">
                Branches
              </Link>
              <Link to="/staff" data-testid="nav-staff">
                Staff
              </Link>
            </nav>
          ) : null}
          {user?.role === 'branch_manager' ? (
            <nav className="app-header__nav" aria-label="Main">
              <Link to="/staff" data-testid="nav-staff">
                Staff
              </Link>
            </nav>
          ) : null}
          {user?.role === 'student' ? (
            <nav className="app-header__nav" aria-label="Main">
              <Link to="/dashboard" data-testid="nav-dashboard">
                Dashboard
              </Link>
            </nav>
          ) : null}
        </div>
        <NotificationBell />
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
