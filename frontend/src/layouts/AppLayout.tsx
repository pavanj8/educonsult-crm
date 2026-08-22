import { Link, Outlet } from 'react-router-dom'

import NotificationBell from '../components/notifications/NotificationBell'
import { useAuth } from '../store/authStore'
import { useBranding } from '../store/brandingStore'

export default function AppLayout() {
  const { user } = useAuth()
  const { brandColor, logoUrl, tenantName } = useBranding()

  // When the tenant has uploaded a logo, show it next to (or instead of)
  // the platform wordmark so the chrome carries the tenant identity.
  // The header still falls back to the platform wordmark when no logo
  // has been uploaded yet so the app remains usable.
  const showLogo = logoUrl !== null
  const heading = tenantName ?? 'EduConsult CRM'

  return (
    <div className="app-layout" data-testid="app-layout">
      <header className="app-header" data-testid="app-header">
        <div className="app-header__brand">
          {showLogo ? (
            <img
              className="app-header__logo"
              data-testid="app-header-logo"
              src={logoUrl}
              alt={`${heading} logo`}
            />
          ) : null}
          <h1>{heading}</h1>
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
          {user?.role === 'document_verifier' ? (
            <nav className="app-header__nav" aria-label="Main">
              <Link to="/verifier" data-testid="nav-verifier">
                Verifier queue
              </Link>
            </nav>
          ) : null}
          {user?.role === 'counselor' ? (
            <nav className="app-header__nav" aria-label="Main">
              <Link to="/my-applications" data-testid="nav-my-applications">
                My applications
              </Link>
            </nav>
          ) : null}
          {/* Indicator that survives even when no branding is applied;
              used by tests + ops to confirm the provider is mounted. */}
          {brandColor !== null ? (
            <span className="app-header__branded" data-testid="app-header-branded">
              Branded
            </span>
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
