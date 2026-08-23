import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import { BrandingProvider } from '../store/brandingStore'
import { AppRoutes } from './index'
import { REGISTER_PATH } from './paths'
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

const mockBranchManager = {
  id: 20,
  email: 'manager@demo.test',
  role: 'branch_manager' as const,
  tenant_id: 10,
  branch_id: 1,
}

const mockStudent = {
  id: 42,
  email: 'student@demo.test',
  role: 'student' as const,
  tenant_id: 10,
  branch_id: 1,
}

const mockReceptionist = {
  id: 7,
  email: 'receptionist@demo.test',
  role: 'receptionist' as const,
  tenant_id: 10,
  branch_id: 1,
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
      <BrandingProvider>
        <MemoryRouter initialEntries={[path]}>
          <LocationStateProbe />
          <AppRoutes />
        </MemoryRouter>
      </BrandingProvider>
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

  it('renders the registration page directly without auth', async () => {
    renderAppAt(REGISTER_PATH)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create student account' })).toBeInTheDocument()
    })
    expect(screen.getByTestId('register-email')).toBeInTheDocument()
    expect(screen.queryByText('Welcome to EduConsult CRM')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Notifications' })).not.toBeInTheDocument()
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

  it('renders staff page for consultancy owner users', async () => {
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

    renderAppAt('/staff')

    await waitFor(() => {
      expect(screen.getByTestId('staff-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Staff' })).toBeInTheDocument()
  })

  it('renders staff page for branch manager users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockBranchManager,
    }) as typeof fetch

    renderAppAt('/staff')

    await waitFor(() => {
      expect(screen.getByTestId('staff-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Staff' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Branches' })).not.toBeInTheDocument()
  })

  it('denies staff page to non-manager users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAppAt('/staff')

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('staff-page')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Staff' })).not.toBeInTheDocument()
  })

  it('renders master data page for consultancy owner users', async () => {
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
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      }) as typeof fetch

    renderAppAt('/master-data')

    await waitFor(() => {
      expect(screen.getByTestId('master-data-admin-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Master data' })).toBeInTheDocument()
  })

  it('renders master data page for branch manager users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranchManager,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      }) as typeof fetch

    renderAppAt('/master-data')

    await waitFor(() => {
      expect(screen.getByTestId('master-data-admin-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Master data' })).toBeInTheDocument()
  })

  it('denies master data page to counselor users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAppAt('/master-data')

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('master-data-admin-page')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Master data' })).not.toBeInTheDocument()
  })

  it('renders checklist templates page for consultancy owner users', async () => {
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
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      }) as typeof fetch

    renderAppAt('/checklist-templates')

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Checklist templates' })).toBeInTheDocument()
  })

  it('renders checklist templates page for branch manager users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranchManager,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      }) as typeof fetch

    renderAppAt('/checklist-templates')

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Checklist templates' })).toBeInTheDocument()
  })

  it('denies checklist templates page to counselor users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAppAt('/checklist-templates')

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('checklist-templates-page')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Checklist templates' })).not.toBeInTheDocument()
  })

  it('renders student dashboard for student users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockStudent,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      }) as typeof fetch

    renderAppAt('/dashboard')

    await waitFor(() => {
      expect(screen.getByTestId('student-dashboard-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('denies student dashboard to non-student users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAppAt('/dashboard')

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('student-dashboard-page')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument()
  })

  it('renders receptionist intake page for receptionist users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockReceptionist,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => null,
      }) as typeof fetch

    renderAppAt('/receptionist/intake')

    await waitFor(() => {
      expect(screen.getByTestId('receptionist-intake-page')).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: 'Intake' })).toBeInTheDocument()
  })

  it('denies receptionist intake page to non-receptionist users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAppAt('/receptionist/intake')

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('receptionist-intake-page')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Intake' })).not.toBeInTheDocument()
  })
})
