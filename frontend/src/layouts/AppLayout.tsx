import { Link, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import LanguageSwitcher from '../components/i18n/LanguageSwitcher'
import AccountMenu from '../components/auth/AccountMenu'
import NotificationBell from '../components/notifications/NotificationBell'
import {
  CHECKLIST_TEMPLATES_PATH,
  MASTER_DATA_ADMIN_PATH,
  TENANT_BRANDING_PATH,
  VISA_DASHBOARD_PATH,
} from '../routes/paths'
import { useAuth } from '../store/authStore'
import { useBranding } from '../store/brandingStore'

export default function AppLayout() {
  const { user } = useAuth()
  const { brandColor, logoUrl, tenantName } = useBranding()
  const { t } = useTranslation()

  // When the tenant has uploaded a logo, show it next to (or instead of)
  // the platform wordmark so the chrome carries the tenant identity.
  // The header still falls back to the platform wordmark when no logo
  // has been uploaded yet so the app remains usable.
  const showLogo = logoUrl !== null
  const heading = tenantName ?? t('app.platformName')

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
            <nav className="app-header__nav" aria-label={t('app.nav.main')}>
              <Link to="/tenants" data-testid="nav-tenants">
                {t('app.nav.tenants')}
              </Link>
            </nav>
          ) : null}
          {user?.role === 'consultancy_owner' ? (
            <nav className="app-header__nav" aria-label={t('app.nav.main')}>
              <Link to="/branches" data-testid="nav-branches">
                {t('app.nav.branches')}
              </Link>
              <Link to="/staff" data-testid="nav-staff">
                {t('app.nav.staff')}
              </Link>
              <Link to={MASTER_DATA_ADMIN_PATH} data-testid="nav-master-data">
                {t('app.nav.masterData')}
              </Link>
              <Link to={TENANT_BRANDING_PATH} data-testid="nav-branding">
                {t('app.nav.branding')}
              </Link>
              <Link
                to={CHECKLIST_TEMPLATES_PATH}
                data-testid="nav-checklist-templates"
              >
                {t('app.nav.checklistTemplates')}
              </Link>
            </nav>
          ) : null}
          {user?.role === 'branch_manager' ? (
            <nav className="app-header__nav" aria-label={t('app.nav.main')}>
              <Link to="/staff" data-testid="nav-staff">
                {t('app.nav.staff')}
              </Link>
              <Link to={MASTER_DATA_ADMIN_PATH} data-testid="nav-master-data">
                {t('app.nav.masterData')}
              </Link>
              <Link
                to={CHECKLIST_TEMPLATES_PATH}
                data-testid="nav-checklist-templates"
              >
                {t('app.nav.checklistTemplates')}
              </Link>
            </nav>
          ) : null}
          {user?.role === 'student' ? (
            <nav className="app-header__nav" aria-label={t('app.nav.main')}>
              <Link to="/dashboard" data-testid="nav-dashboard">
                {t('app.nav.dashboard')}
              </Link>
            </nav>
          ) : null}
          {user?.role === 'document_verifier' ? (
            <nav className="app-header__nav" aria-label={t('app.nav.main')}>
              <Link to="/verifier" data-testid="nav-verifier">
                {t('app.nav.verifierQueue')}
              </Link>
            </nav>
          ) : null}
          {user?.role === 'counselor' ? (
            <nav className="app-header__nav" aria-label={t('app.nav.main')}>
              <Link to="/my-applications" data-testid="nav-my-applications">
                {t('app.nav.myApplications')}
              </Link>
            </nav>
          ) : null}
          {user?.role === 'receptionist' ? (
            <nav className="app-header__nav" aria-label={t('app.nav.main')}>
              <Link to="/receptionist/intake" data-testid="nav-receptionist-intake">
                {t('app.nav.intake')}
              </Link>
            </nav>
          ) : null}
          {user?.role === 'visa_processor' ? (
            <nav className="app-header__nav" aria-label={t('app.nav.main')}>
              <Link to={VISA_DASHBOARD_PATH} data-testid="nav-visa">
                {t('app.nav.visaQueue')}
              </Link>
            </nav>
          ) : null}
        </div>
        <div className="app-header__actions">
          <LanguageSwitcher />
          <NotificationBell />
          <AccountMenu />
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
