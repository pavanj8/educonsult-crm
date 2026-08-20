import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import BranchesPage from './BranchesPage'

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

describe('BranchesPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders branch list after loading', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockBranches,
    }) as typeof fetch

    render(<BranchesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('branch-table')).toBeInTheDocument()
    })

    expect(screen.getByText('Mumbai HQ')).toBeInTheDocument()
    expect(screen.getByText('Delhi Center')).toBeInTheDocument()
    expect(screen.getByText('Mumbai')).toBeInTheDocument()
    expect(screen.getByText('Delhi')).toBeInTheDocument()
  })

  it('shows empty state when no branches exist', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    }) as typeof fetch

    render(<BranchesPage />)

    await waitFor(() => {
      expect(screen.getByText('No branches yet.')).toBeInTheDocument()
    })
  })

  it('shows error when API returns 403', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    render(<BranchesPage />)

    await waitFor(() => {
      expect(screen.getByText('You do not have permission to view branches')).toBeInTheDocument()
    })
  })

  it('creates a branch and shows success message', async () => {
    const user = userEvent.setup()
    const newBranch = {
      id: 3,
      tenant_id: 10,
      name: 'Bangalore Office',
      city: 'Bangalore',
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => newBranch,
      }) as typeof fetch

    render(<BranchesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('branch-name')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('branch-name'), 'Bangalore Office')
    await user.type(screen.getByTestId('branch-city'), 'Bangalore')
    await user.click(screen.getByTestId('branch-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('branch-create-success')).toBeInTheDocument()
    })

    expect(screen.getByTestId('branch-create-success')).toHaveTextContent(
      'Branch "Bangalore Office" created',
    )
    expect(screen.getByText('Bangalore Office')).toBeInTheDocument()
  })

  it('shows create error from API', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: 'Branch name is required' }),
      }) as typeof fetch

    render(<BranchesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('branch-name')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('branch-name'), 'Invalid')
    await user.type(screen.getByTestId('branch-city'), 'City')
    await user.click(screen.getByTestId('branch-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('branch-create-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('branch-create-error')).toHaveTextContent('Branch name is required')
  })

  it('opens edit form and updates a branch', async () => {
    const user = userEvent.setup()
    const updatedBranch = {
      ...mockBranches[0],
      name: 'Mumbai Main',
      updated_at: '2026-02-02T10:00:00Z',
    }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => updatedBranch,
      }) as typeof fetch

    render(<BranchesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('branch-edit-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('branch-edit-1'))

    expect(screen.getByTestId('branch-edit-name')).toHaveValue('Mumbai HQ')
    expect(screen.getByTestId('branch-edit-city')).toHaveValue('Mumbai')

    await user.clear(screen.getByTestId('branch-edit-name'))
    await user.type(screen.getByTestId('branch-edit-name'), 'Mumbai Main')
    await user.click(screen.getByTestId('branch-edit-submit'))

    await waitFor(() => {
      expect(screen.queryByTestId('branch-edit-name')).not.toBeInTheDocument()
    })

    expect(screen.getByText('Mumbai Main')).toBeInTheDocument()
  })

  it('shows update error from API', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Branch not found' }),
      }) as typeof fetch

    render(<BranchesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('branch-edit-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('branch-edit-1'))
    await user.click(screen.getByTestId('branch-edit-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('branch-edit-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('branch-edit-error')).toHaveTextContent('Branch not found')
  })

  it('cancels edit form', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockBranches,
    }) as typeof fetch

    render(<BranchesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('branch-edit-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('branch-edit-1'))
    expect(screen.getByTestId('branch-edit-name')).toBeInTheDocument()

    await user.click(screen.getByTestId('branch-edit-cancel'))

    expect(screen.queryByTestId('branch-edit-name')).not.toBeInTheDocument()
  })
})
