import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import AppLayout from './AppLayout'
import { AuthProvider } from '../store/authStore'
import { BrandingProvider } from '../store/brandingStore'

const superAdminUser = {
  id: 1,
  email: 'admin@demo.test',
  role: 'super_admin' as const,
  tenant_id: 7,
  branch_id: null,
}

const ownerUser = {
  id: 2,
  email: 'owner@demo.test',
  role: 'consultancy_owner' as const,
  tenant_id: 7,
  branch_id: null,
}

const brandedTenant = {
  id: 7,
  name: 'Apex EduConsult',
  slug: 'apex',
  logo_url: 'https://cdn.example.test/apex/logo.png',
  brand_color: '#1A2B3C',
  currency: 'USD',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

const emptyNotifications = { items: [], unread_count: 0 }

function LayoutHarness({ children }: { children?: ReactNode }) {
  return (
    <AuthProvider>
      <BrandingProvider>
        <MemoryRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route
                index
                element={<div data-testid="layout-content">outlet</div>}
              />
            </Route>
          </Routes>
          {children}
        </MemoryRouter>
      </BrandingProvider>
    </AuthProvider>
  )
}

type JsonValue = unknown
type MockResponse = { ok: boolean; status: number; json: () => Promise<JsonValue> }

/**
 * URL-aware fetch mock. ``NotificationBell`` fires its own
 * ``/notifications`` request on mount, which races with the
 * ``AuthProvider``'s ``/auth/me`` and the hook's ``/tenants/{id}``
 * requests; routing by URL keeps the test stable regardless of the
 * mount order.
 */
function setupFetchMock(
  fetchSpy: ReturnType<typeof vi.spyOn>,
  routes: Record<string, MockResponse | (() => MockResponse)>,
): void {
  fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString()
    for (const [prefix, response] of Object.entries(routes)) {
      if (url.includes(prefix)) {
        const value = typeof response === 'function' ? response() : response
        return {
          ok: value.ok,
          status: value.status,
          json: value.json,
        } as Response
      }
    }
    throw new Error(`Unexpected fetch in test: ${url}`)
  })
}

describe('AppLayout — brand color theming (E10 / J3 / #113)', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    document.documentElement.removeAttribute('style')
    fetchSpy = vi.spyOn(globalThis, 'fetch')
  })

  afterEach(() => {
    fetchSpy.mockRestore()
    document.documentElement.removeAttribute('style')
  })

  it('falls back to the default wordmark when no tenant branding is available', async () => {
    setupFetchMock(fetchSpy, {
      '/auth/me': {
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Unauthenticated' }),
      },
    })

    render(
      <LayoutHarness>
        <div data-testid="fallback-marker" />
      </LayoutHarness>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('fallback-marker')).toBeInTheDocument()
    })

    const layout = screen.getByTestId('app-layout')
    expect(screen.getByRole('heading', { name: 'EduConsult CRM' })).toBeInTheDocument()
    expect(screen.queryByTestId('app-header-logo')).not.toBeInTheDocument()
    expect(layout.getAttribute('data-app-header-branded')).toBe('false')
    expect(document.documentElement.style.getPropertyValue('--brand-color')).toBe('')
  })

  it('renders the tenant name and logo when branding is available', async () => {
    localStorage.setItem('access_token', 'test-token')
    setupFetchMock(fetchSpy, {
      '/auth/me': {
        ok: true,
        status: 200,
        json: async () => superAdminUser,
      },
      '/tenants/7': {
        ok: true,
        status: 200,
        json: async () => brandedTenant,
      },
      '/notifications': {
        ok: true,
        status: 200,
        json: async () => emptyNotifications,
      },
    })

    render(<LayoutHarness />)

    // The CSS-variable side-effect on ``document.documentElement`` is
    // the deterministic signal that the provider has finished
    // loading. Wait for it before asserting on rendered nodes.
    await waitFor(() => {
      expect(
        document.documentElement.style.getPropertyValue('--brand-color'),
      ).toBe('#1A2B3C')
    })

    const layout = screen.getByTestId('app-layout')
    expect(layout.getAttribute('data-app-header-branded')).toBe('true')
    expect(
      screen.getByRole('heading', { name: 'Apex EduConsult' }),
    ).toBeInTheDocument()
    const logo = screen.getByTestId('app-header-logo')
    expect(logo).toHaveAttribute('src', 'https://cdn.example.test/apex/logo.png')
    expect(logo).toHaveAttribute('alt', 'Apex EduConsult logo')
    expect(logo).toHaveAttribute('referrerPolicy', 'no-referrer')
    expect(logo).toHaveAttribute('loading', 'lazy')

    expect(document.documentElement.style.getPropertyValue('--brand-color')).toBe('#1A2B3C')
    expect(
      document.documentElement.style.getPropertyValue('--brand-color-contrast'),
    ).toBe('#ffffff')
  })

  it('does NOT throw when rendering for an owner whose role lacks TENANT_READ', async () => {
    // ``CONSULTANCY_OWNER`` has TENANT_UPDATE but not TENANT_READ, so
    // the GET /tenants/{id} request surfaces a 403. The layout must
    // still render (with the platform-default wordmark) rather than
    // crash the navigation chrome.
    setupFetchMock(fetchSpy, {
      '/auth/me': {
        ok: true,
        status: 200,
        json: async () => ownerUser,
      },
      '/tenants/7': {
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Insufficient permissions' }),
      },
      '/notifications': {
        ok: true,
        status: 200,
        json: async () => emptyNotifications,
      },
    })

    render(<LayoutHarness />)

    // Wait for the branding fetch to fire and settle.
    await waitFor(() => {
      expect(
        fetchSpy.mock.calls.some((call: unknown[]) => {
          const url = call[0]
          return typeof url === 'string' && url.includes('/tenants/7')
        }),
      ).toBe(true)
    })

    await waitFor(() => {
      expect(screen.getByTestId('app-header')).toBeInTheDocument()
    })

    const layout = screen.getByTestId('app-layout')
    // No branding applied -> default wordmark, no logo, no branded
    // marker, no CSS variable set.
    expect(screen.getByRole('heading', { name: 'EduConsult CRM' })).toBeInTheDocument()
    expect(screen.queryByTestId('app-header-logo')).not.toBeInTheDocument()
    expect(layout.getAttribute('data-app-header-branded')).toBe('false')
    expect(document.documentElement.style.getPropertyValue('--brand-color')).toBe('')
  })

  it('clears the brand color CSS variable when branding is removed (logout)', async () => {
    setupFetchMock(fetchSpy, {
      '/auth/me': {
        ok: true,
        status: 200,
        json: async () => superAdminUser,
      },
      '/tenants/7': {
        ok: true,
        status: 200,
        json: async () => brandedTenant,
      },
      '/notifications': {
        ok: true,
        status: 200,
        json: async () => emptyNotifications,
      },
    })

    const { unmount } = render(<LayoutHarness />)

    await waitFor(() => {
      expect(document.documentElement.style.getPropertyValue('--brand-color')).toBe('#1A2B3C')
    })

    unmount()

    expect(document.documentElement.style.getPropertyValue('--brand-color')).toBe('')
    expect(
      document.documentElement.style.getPropertyValue('--brand-color-contrast'),
    ).toBe('')
  })
})
