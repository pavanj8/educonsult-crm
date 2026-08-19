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
