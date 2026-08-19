import { render, screen, waitFor } from '@testing-library/react'
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
})
