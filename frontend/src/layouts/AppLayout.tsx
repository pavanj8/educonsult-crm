import { Link, Outlet } from 'react-router-dom'
import type { ReactNode } from 'react'

import NotificationBell from '../components/notifications/NotificationBell'
import { CHECKLIST_TEMPLATES_PATH, MASTER_DATA_ADMIN_PATH } from '../routes/paths'
import { useAuth } from '../store/authStore'
import { useBranding } from '../store/brandingStore'

interface NavLinkSpec {
  to: string
  testId: string
  label: string
}

/**
 * Role-keyed top-level nav (E15). Consultancy owner + branch manager
 * share the same admin-tools nav block — they both carry
 * ``checklist_template:manage`` and ``master_data:manage`` — so
 * keying the links by role keeps the markup DRY when the E15 epic
 * adds more admin tools. Each role still owns its links (e.g.
 * consultancy owners additionally see ``/branches``).
 */
const ADMIN_NAV_LINKS: Record<'consultancy_owner' | 'branch_manager', NavLinkSpec[]> = {
  consultancy_owner: [
    { to: '/branches', testId: 'nav-branches', label: 'Branches' },
    { to: '/staff', testId: 'nav-staff', label: 'Staff' },
    { to: MASTER_DATA_ADMIN_PATH, testId: 'nav-master-data', label: 'Master data' },
    {
      to: CHECKLIST_TEMPLATES_PATH,
      testId: 'nav-checklist-templates',
      label: 'Checklist templates',
    },
  ],
  branch_manager: [
    { to: '/staff', testId: 'nav-staff', label: 'Staff' },
    { to: MASTER_DATA_ADMIN_PATH, testId: 'nav-master-data', label: 'Master data' },
    {
      to: CHECKLIST_TEMPLATES_PATH,
      testId: 'nav-checklist-templates',
      label: 'Checklist templates',
    },
  ],
}

function NavLinks({ links }: { links: NavLinkSpec[] }): ReactNode {
  return (
    <nav className="app-header__nav" aria-label="Main">
      {links.map((link) => (
        <Link key={link.testId} to={link.to} data-testid={link.testId}>
          {link.label}
        </Link>
      ))}
    </nav>
  )
}

export default function AppLayout() {
  const { user } = useAuth()
  const { brandColor, logoUrl, tenantName } = useBranding()

  // When the tenant has uploaded a logo, show it next to (or instead of)
  // the platform wordmark so the chrome carries the tenant identity.
  // The header still falls back to the platform wordmark when no logo
  // has been uploaded yet so the app remains usable.
  const showLogo = logoUrl !== null
  const heading = tenantName ?? 'EduConsult CRM'

  // Pick the role-specific nav. Non-admins get a single-link nav.
  let navLinks: NavLinkSpec[] | null = null
  if (user?.role === 'super_admin') {
    navLinks = [{ to: '/tenants', testId: 'nav-tenants', label: 'Tenants' }]
  } else if (user?.role === 'consultancy_owner' || user?.role === 'branch_manager') {
    navLinks = ADMIN_NAV_LINKS[user.role]
  } else if (user?.role === 'student') {
    navLinks = [{ to: '/dashboard', testId: 'nav-dashboard', label: 'Dashboard' }]
  } else if (user?.role === 'document_verifier') {
    navLinks = [{ to: '/verifier', testId: 'nav-verifier', label: 'Verifier queue' }]
  } else if (user?.role === 'counselor') {
    navLinks = [
      { to: '/my-applications', testId: 'nav-my-applications', label: 'My applications' },
    ]
  }

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
          {navLinks !== null ? <NavLinks links={navLinks} /> : null}
        </div>
        <NotificationBell />
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
