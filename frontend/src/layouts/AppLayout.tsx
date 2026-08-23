import { Link, Outlet } from 'react-router-dom'

import NotificationBell from '../components/notifications/NotificationBell'
import { MASTER_DATA_ADMIN_PATH, TENANT_BRANDING_PATH } from '../routes/paths'
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

  // ``data-app-header-branded`` mirrors the brand-color side-effect
  // for tests + ops so the provider's mounted state is observable
  // without rendering a user-visible chip in the chrome.
  return (
    <div
      className="app-layout"
      data-testid="app-layout"
      data-app-header-branded={brandColor !== null ? 'true' : 'false'}
    >
      <header className="app-header" data-testid="app-header">
        <div className="app-header__brand">
          {showLogo ? (
            <img
              className="app-header__logo"
              data-testid="app-header-logo"
              src={logoUrl}
              // The adjacent <h1> already carries the tenant
              // name, so the logo is decorative — hide it from
              // screen readers and avoid announcing the brand
              // identity twice on every page header.
              alt=""
              aria-hidden="true"
              // Tenant controls the logo URL (up to https://), so opt
              // out of the default referrer policy to avoid leaking
              // the user's IP / UA to a third-party image host.
              referrerPolicy="no-referrer"
              loading="lazy"
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
              <Link to={MASTER_DATA_ADMIN_PATH} data-testid="nav-master-data">
                Master data
              </Link>
              <Link to={TENANT_BRANDING_PATH} data-testid="nav-branding">
                Branding
              </Link>
            </nav>
          ) : null}
          {user?.role === 'branch_manager' ? (
            <nav className="app-header__nav" aria-label="Main">
              <Link to="/staff" data-testid="nav-staff">
                Staff
              </Link>
              <Link to={MASTER_DATA_ADMIN_PATH} data-testid="nav-master-data">
                Master data
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
        </div>
        <NotificationBell />
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
