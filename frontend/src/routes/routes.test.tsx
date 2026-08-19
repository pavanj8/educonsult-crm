import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import { AppRoutes } from './index'
import { LOGIN_PATH } from './ProtectedRoute'

const mockUser = {
  id: 1,
  email: 'counselor@demo.test',
  role: 'counselor' as const,
  tenant_id: 10,
  branch_id: 1,
}

const mockSuperAdmin = {
  id: 99,
  email: 'super_admin@demo.test',
  role: 'super_admin' as const,
  tenant_id: null,
  branch_id: null,
}

const mockConsultancyOwner = {
  id: 50,
  email: 'owner@demo.test',
  role: 'consultancy_owner' as const,
  tenant_id: 10,
  branch_id: null,
}

function LocationStateProbe() {
  const location = useLocation()
  const fromPath =
    location.state && typeof location.state === 'object' && 'from' in location.state
      ? (location.state.from as { pathname?: string }).pathname ?? ''
      : ''

  return <div data-testid="redirect-from">{fromPath}</div>
}

function renderAppAt(path: string) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[path]}>
        <LocationStateProbe />
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('AppRouter routes', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('redirects unauthenticated users to the public login page', async () => {
    renderAppAt('/')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })
    expect(screen.getByTestId('login-email')).toBeInTheDocument()
    expect(screen.queryByText('Welcome to EduConsult CRM')).not.toBeInTheDocument()
  })

  it('renders the login page directly without auth', async () => {
    renderAppAt(LOGIN_PATH)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })
    expect(screen.queryByText('Welcome to EduConsult CRM')).not.toBeInTheDocument()
  })

  it('redirects unauthenticated deep links to login with return path in state', async () => {
    renderAppAt('/students/42')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    expect(screen.getByTestId('redirect-from')).toHaveTextContent('/students/42')
  })

  it('renders the app layout and home page for authenticated users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAppAt('/')

    await waitFor(() => {
      expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    })

    expect(screen.getByRole('heading', { name: 'EduConsult CRM' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('renders the not found page for unknown authenticated routes', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAppAt('/unknown-route')

    await waitFor(() => {
      expect(screen.getByText('Page not found')).toBeInTheDocument()
    })
  })

  it('renders the login page at /login without the app layout', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Not authenticated' }),
    }) as typeof fetch

    renderAppAt('/login')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Notifications' })).not.toBeInTheDocument()
  })

  it('renders tenants page for super admin users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockSuperAdmin,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      }) as typeof fetch

    renderAppAt('/tenants')

    await waitFor(() => {
      expect(screen.getByTestId('tenants-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Tenants' })).toBeInTheDocument()
  })

  it('denies tenants page to non-super-admin users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAppAt('/tenants')

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('tenants-page')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Tenants' })).not.toBeInTheDocument()
  })

  it('renders branches page for consultancy owner users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockConsultancyOwner,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      }) as typeof fetch

    renderAppAt('/branches')

    await waitFor(() => {
      expect(screen.getByTestId('branches-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Branches' })).toBeInTheDocument()
  })

  it('denies branches page to non-consultancy-owner users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAppAt('/branches')

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('branches-page')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Branches' })).not.toBeInTheDocument()
  })
})
