import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import StaffPage from './StaffPage'

const mockOwner = {
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

const mockBranchManagerNoBranch = {
  id: 21,
  email: 'manager.no-branch@demo.test',
  role: 'branch_manager' as const,
  tenant_id: 10,
  branch_id: null,
}

const mockBranches = [
  {
    id: 1,
    tenant_id: 10,
    name: 'Mumbai HQ',
    city: 'Mumbai',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 2,
    tenant_id: 10,
    name: 'Delhi Center',
    city: 'Delhi',
    created_at: '2026-01-20T10:00:00Z',
    updated_at: '2026-01-20T10:00:00Z',
  },
]

const mockStaffList = [
  {
    id: 5,
    email: 'existing.counselor@example.test',
    role: 'counselor' as const,
    tenant_id: 10,
    branch_id: 1,
    is_active: true,
    created_at: '2026-01-10T10:00:00Z',
    updated_at: '2026-01-10T10:00:00Z',
  },
  {
    id: 6,
    email: 'inactive.receptionist@example.test',
    role: 'receptionist' as const,
    tenant_id: 10,
    branch_id: 1,
    is_active: false,
    created_at: '2026-01-11T10:00:00Z',
    updated_at: '2026-01-12T10:00:00Z',
  },
]

function createFetchMock(handlers: {
  user: typeof mockOwner | typeof mockBranchManager | typeof mockBranchManagerNoBranch
  staffList?: typeof mockStaffList
  createdStaff?: Record<string, unknown>
  updatedStaff?: Record<string, unknown>
  deactivatedStaff?: Record<string, unknown>
  reactivatedStaff?: Record<string, unknown>
  createConflict?: boolean
  statusConflict?: boolean
}) {
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = String(url)

    if (path.includes('/auth/me')) {
      return {
        ok: true,
        status: 200,
        json: async () => handlers.user,
      }
    }

    if (path.endsWith('/staff') && init?.method === 'POST') {
      if (handlers.createConflict) {
        return {
          ok: false,
          status: 409,
          json: async () => ({ detail: 'A user with this email already exists' }),
        }
      }
      return {
        ok: true,
        status: 201,
        json: async () => handlers.createdStaff,
      }
    }

    if (path.match(/\/staff\/\d+$/) && init?.method === 'PATCH') {
      return {
        ok: true,
        status: 200,
        json: async () => handlers.updatedStaff,
      }
    }

    if (path.match(/\/staff\/\d+\/deactivate$/) && init?.method === 'POST') {
      if (handlers.statusConflict) {
        return {
          ok: false,
          status: 409,
          json: async () => ({ detail: 'Staff member is already inactive' }),
        }
      }
      return {
        ok: true,
        status: 200,
        json: async () => handlers.deactivatedStaff,
      }
    }

    if (path.match(/\/staff\/\d+\/reactivate$/) && init?.method === 'POST') {
      return {
        ok: true,
        status: 200,
        json: async () => handlers.reactivatedStaff,
      }
    }

    if (path.match(/\/staff\/\d+$/) && (!init?.method || init.method === 'GET')) {
      return {
        ok: true,
        status: 200,
        json: async () => mockStaffList[0],
      }
    }

    if (path.endsWith('/staff')) {
      return {
        ok: true,
        status: 200,
        json: async () => handlers.staffList ?? mockStaffList,
      }
    }

    if (path.endsWith('/branches')) {
      return {
        ok: true,
        status: 200,
        json: async () => mockBranches,
      }
    }

    throw new Error(`Unhandled fetch: ${path} ${init?.method ?? 'GET'}`)
  }) as typeof fetch
}

function renderStaffPage() {
  return render(
    <AuthProvider>
      <StaffPage />
    </AuthProvider>,
  )
}

describe('StaffPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders create form for consultancy owner with branch selector', async () => {
    globalThis.fetch = createFetchMock({ user: mockOwner })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-branch')).toBeInTheDocument()
    })

    expect(screen.getByTestId('staff-role')).toBeInTheDocument()
    expect(screen.queryByTestId('staff-branch-readonly')).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Select a branch' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Branch Manager' })).toBeInTheDocument()
  })

  it('creates staff as consultancy owner and shows success message', async () => {
    const user = userEvent.setup()
    const createdStaff = {
      id: 42,
      email: 'new.counselor@example.test',
      role: 'counselor' as const,
      tenant_id: 10,
      branch_id: 2,
      is_active: true,
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    }
    globalThis.fetch = createFetchMock({ user: mockOwner, createdStaff })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-branch')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('staff-email'), 'new.counselor@example.test')
    await user.type(screen.getByTestId('staff-password'), 'secure-password')
    await user.selectOptions(screen.getByTestId('staff-role'), 'counselor')
    await user.selectOptions(screen.getByTestId('staff-branch'), '2')
    await user.click(screen.getByTestId('staff-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('staff-create-success')).toBeInTheDocument()
    })

    expect(screen.getByTestId('staff-create-success')).toHaveTextContent(
      'Staff account for new.counselor@example.test (Counselor) created',
    )

    const staffCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      ([url, init]) =>
        typeof url === 'string' &&
        url.endsWith('/staff') &&
        (init as RequestInit | undefined)?.method === 'POST',
    )
    expect(staffCalls).toHaveLength(1)
    const requestInit = staffCalls[0]?.[1] as RequestInit
    expect(JSON.parse(String(requestInit.body))).toMatchObject({
      email: 'new.counselor@example.test',
      role: 'counselor',
      branch_id: 2,
    })
  })

  it('shows create error from API', async () => {
    const user = userEvent.setup()
    globalThis.fetch = createFetchMock({ user: mockOwner, createConflict: true })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-branch')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('staff-email'), 'existing@example.test')
    await user.type(screen.getByTestId('staff-password'), 'secure-password')
    await user.selectOptions(screen.getByTestId('staff-branch'), '1')
    await user.click(screen.getByTestId('staff-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('staff-create-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('staff-create-error')).toHaveTextContent(
      'A user with this email already exists',
    )
  })

  it('renders branch manager form without branch selector or branch manager role', async () => {
    globalThis.fetch = createFetchMock({ user: mockBranchManager })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-branch-readonly')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('staff-branch')).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Branch Manager' })).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Counselor' })).toBeInTheDocument()
    expect(screen.getByTestId('staff-branch-readonly')).toHaveTextContent(
      'Staff will be assigned to your branch',
    )
    expect(screen.getByTestId('staff-branch-readonly')).not.toHaveTextContent('ID:')
  })

  it('disables create submit for branch manager without branch assignment', async () => {
    globalThis.fetch = createFetchMock({ user: mockBranchManagerNoBranch })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-create-submit')).toBeDisabled()
    })

    expect(screen.getByTestId('staff-branch-readonly')).toHaveTextContent(
      'not assigned to a branch',
    )
  })

  it('creates staff as branch manager using own branch id', async () => {
    const user = userEvent.setup()
    const createdStaff = {
      id: 43,
      email: 'receptionist@example.test',
      role: 'receptionist' as const,
      tenant_id: 10,
      branch_id: 1,
      is_active: true,
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    }
    globalThis.fetch = createFetchMock({ user: mockBranchManager, createdStaff })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-branch-readonly')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('staff-email'), 'receptionist@example.test')
    await user.type(screen.getByTestId('staff-password'), 'secure-password')
    await user.selectOptions(screen.getByTestId('staff-role'), 'receptionist')
    await user.click(screen.getByTestId('staff-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('staff-create-success')).toBeInTheDocument()
    })

    const staffCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      ([url, init]) =>
        typeof url === 'string' &&
        url.endsWith('/staff') &&
        (init as RequestInit | undefined)?.method === 'POST',
    )
    expect(staffCalls).toHaveLength(1)
    const requestInit = staffCalls[0]?.[1] as RequestInit
    expect(JSON.parse(String(requestInit.body))).toMatchObject({
      email: 'receptionist@example.test',
      role: 'receptionist',
      branch_id: 1,
    })
  })

  it('loads edit form for existing staff and updates role and branch', async () => {
    const user = userEvent.setup()
    const updatedStaff = {
      ...mockStaffList[0],
      role: 'receptionist' as const,
      branch_id: 2,
    }
    globalThis.fetch = createFetchMock({ user: mockOwner, updatedStaff })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-edit-5')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('staff-edit-5'))

    await waitFor(() => {
      expect(screen.getByTestId('staff-edit-email')).toHaveValue('existing.counselor@example.test')
    })

    await user.selectOptions(screen.getByTestId('staff-edit-role'), 'receptionist')
    await user.selectOptions(screen.getByTestId('staff-edit-branch'), '2')
    await user.click(screen.getByTestId('staff-edit-submit'))

    await waitFor(() => {
      expect(screen.queryByTestId('staff-edit-email')).not.toBeInTheDocument()
      expect(screen.getByTestId('staff-row-5')).toHaveTextContent('Receptionist')
      expect(screen.getByTestId('staff-row-5')).toHaveTextContent('Delhi Center')
    })

    const patchCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      ([url, init]) =>
        typeof url === 'string' &&
        url.endsWith('/staff/5') &&
        (init as RequestInit | undefined)?.method === 'PATCH',
    )
    expect(patchCalls).toHaveLength(1)
    const requestInit = patchCalls[0]?.[1] as RequestInit
    expect(JSON.parse(String(requestInit.body))).toMatchObject({
      role: 'receptionist',
      branch_id: 2,
    })
  })

  it('shows active and inactive status in staff list', async () => {
    globalThis.fetch = createFetchMock({ user: mockOwner })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-status-5')).toHaveTextContent('Active')
      expect(screen.getByTestId('staff-status-6')).toHaveTextContent('Inactive')
    })

    expect(screen.getByTestId('staff-toggle-5')).toHaveTextContent('Deactivate')
    expect(screen.getByTestId('staff-toggle-6')).toHaveTextContent('Reactivate')
  })

  it('deactivates staff from list and shows success message', async () => {
    const user = userEvent.setup()
    const deactivatedStaff = {
      ...mockStaffList[0],
      is_active: false,
    }
    globalThis.fetch = createFetchMock({ user: mockOwner, deactivatedStaff })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-toggle-5')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('staff-toggle-5'))

    await waitFor(() => {
      expect(screen.getByTestId('staff-status-5')).toHaveTextContent('Inactive')
      expect(screen.getByTestId('staff-toggle-5')).toHaveTextContent('Reactivate')
      expect(screen.getByTestId('staff-status-success')).toHaveTextContent('deactivated')
    })

    const deactivateCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      ([url, init]) =>
        typeof url === 'string' &&
        url.endsWith('/staff/5/deactivate') &&
        (init as RequestInit | undefined)?.method === 'POST',
    )
    expect(deactivateCalls).toHaveLength(1)
  })

  it('reactivates inactive staff from list', async () => {
    const user = userEvent.setup()
    const reactivatedStaff = {
      ...mockStaffList[1],
      is_active: true,
    }
    globalThis.fetch = createFetchMock({ user: mockOwner, reactivatedStaff })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-toggle-6')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('staff-toggle-6'))

    await waitFor(() => {
      expect(screen.getByTestId('staff-status-6')).toHaveTextContent('Active')
      expect(screen.getByTestId('staff-status-success')).toHaveTextContent('reactivated')
    })

    const reactivateCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      ([url, init]) =>
        typeof url === 'string' &&
        url.endsWith('/staff/6/reactivate') &&
        (init as RequestInit | undefined)?.method === 'POST',
    )
    expect(reactivateCalls).toHaveLength(1)
  })

  it('shows status error when deactivation fails', async () => {
    const user = userEvent.setup()
    globalThis.fetch = createFetchMock({ user: mockOwner, statusConflict: true })

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-toggle-5')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('staff-toggle-5'))

    await waitFor(() => {
      expect(screen.getByTestId('staff-status-error')).toHaveTextContent(
        'Staff member is already inactive',
      )
    })
  })
})
