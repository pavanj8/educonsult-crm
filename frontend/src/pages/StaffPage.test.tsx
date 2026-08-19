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
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockOwner,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      }) as typeof fetch

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-branch')).toBeInTheDocument()
    })

    expect(screen.getByTestId('staff-role')).toBeInTheDocument()
    expect(screen.queryByTestId('staff-branch-readonly')).not.toBeInTheDocument()
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
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockOwner,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => createdStaff,
      }) as typeof fetch

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-email')).toBeInTheDocument()
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
  })

  it('shows create error from API', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockOwner,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({ detail: 'A user with this email already exists' }),
      }) as typeof fetch

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-email')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('staff-email'), 'existing@example.test')
    await user.type(screen.getByTestId('staff-password'), 'secure-password')
    await user.click(screen.getByTestId('staff-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('staff-create-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('staff-create-error')).toHaveTextContent(
      'A user with this email already exists',
    )
  })

  it('renders branch manager form without branch selector or branch manager role', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockBranchManager,
    }) as typeof fetch

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-branch-readonly')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('staff-branch')).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Branch Manager' })).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Counselor' })).toBeInTheDocument()
  })

  it('creates staff as branch manager using own branch id', async () => {
    const user = userEvent.setup()
    const createdStaff = {
      id: 43,
      email: 'receptionist@example.test',
      role: 'receptionist' as const,
      tenant_id: 10,
      branch_id: 1,
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranchManager,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => createdStaff,
      }) as typeof fetch

    renderStaffPage()

    await waitFor(() => {
      expect(screen.getByTestId('staff-email')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('staff-email'), 'receptionist@example.test')
    await user.type(screen.getByTestId('staff-password'), 'secure-password')
    await user.selectOptions(screen.getByTestId('staff-role'), 'receptionist')
    await user.click(screen.getByTestId('staff-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('staff-create-success')).toBeInTheDocument()
    })

    const staffCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      ([url]) => typeof url === 'string' && url.includes('/staff'),
    )
    expect(staffCalls).toHaveLength(1)
    const requestInit = staffCalls[0]?.[1] as RequestInit
    expect(JSON.parse(String(requestInit.body))).toMatchObject({
      email: 'receptionist@example.test',
      role: 'receptionist',
      branch_id: 1,
    })
  })
})
