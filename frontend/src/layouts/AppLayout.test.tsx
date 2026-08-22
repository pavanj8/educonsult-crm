import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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

describe('AppLayout — brand color theming (E10 / J3 / #113)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    document.documentElement.removeAttribute('style')
  })

  it('falls back to the default wordmark when no tenant branding is available', async () => {
    render(
      <LayoutHarness>
        <div data-testid="fallback-marker" />
      </LayoutHarness>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('fallback-marker')).toBeInTheDocument()
    })

    expect(screen.getByRole('heading', { name: 'EduConsult CRM' })).toBeInTheDocument()
    expect(screen.queryByTestId('app-header-logo')).not.toBeInTheDocument()
    expect(screen.queryByTestId('app-header-branded')).not.toBeInTheDocument()
    expect(document.documentElement.style.getPropertyValue('--brand-color')).toBe('')
  })

  it('renders the tenant name and logo when branding is available', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => superAdminUser,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => brandedTenant,
      })
      // The notification bell fires its own requests; respond with an
      // empty queue so the layout settles deterministically.
      .mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [], unread_count: 0 }),
      }) as typeof fetch

    render(<LayoutHarness />)

    await waitFor(() => {
      expect(screen.getByTestId('app-header-branded')).toBeInTheDocument()
    })

    expect(
      screen.getByRole('heading', { name: 'Apex EduConsult' }),
    ).toBeInTheDocument()
    const logo = screen.getByTestId('app-header-logo')
    expect(logo).toHaveAttribute('src', 'https://cdn.example.test/apex/logo.png')
    expect(logo).toHaveAttribute('alt', 'Apex EduConsult logo')

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
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ownerUser,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Insufficient permissions' }),
      })
      .mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [], unread_count: 0 }),
      }) as typeof fetch

    render(<LayoutHarness />)

    await waitFor(() => {
      expect(screen.getByTestId('app-header')).toBeInTheDocument()
    })

    // No branding applied -> default wordmark, no logo, no branded
    // chip, no CSS variable set.
    expect(screen.getByRole('heading', { name: 'EduConsult CRM' })).toBeInTheDocument()
    expect(screen.queryByTestId('app-header-logo')).not.toBeInTheDocument()
    expect(screen.queryByTestId('app-header-branded')).not.toBeInTheDocument()
    expect(document.documentElement.style.getPropertyValue('--brand-color')).toBe('')
  })

  it('clears the brand color CSS variable when branding is removed (logout)', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => superAdminUser,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => brandedTenant,
      }) as typeof fetch

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
