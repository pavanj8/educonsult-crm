import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TenantsPage from './TenantsPage'

const mockTenants = [
  {
    id: 1,
    name: 'Apex EduConsult',
    slug: 'apex',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
]

describe('TenantsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders tenant list after loading', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockTenants,
    }) as typeof fetch

    render(<TenantsPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-table')).toBeInTheDocument()
    })

    expect(screen.getByText('Apex EduConsult')).toBeInTheDocument()
    expect(screen.getByText('apex')).toBeInTheDocument()
  })

  it('shows empty state when no tenants exist', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    }) as typeof fetch

    render(<TenantsPage />)

    await waitFor(() => {
      expect(screen.getByText('No tenants yet.')).toBeInTheDocument()
    })
  })

  it('creates a tenant and shows success message', async () => {
    const user = userEvent.setup()
    const newTenant = {
      id: 2,
      name: 'Bright Future',
      slug: 'bright-future',
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTenants,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => newTenant,
      }) as typeof fetch

    render(<TenantsPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-name')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('tenant-name'), 'Bright Future')
    await user.type(screen.getByTestId('tenant-slug'), 'bright-future')
    await user.type(screen.getByTestId('tenant-owner-email'), 'owner@bright.test')
    await user.click(screen.getByTestId('tenant-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('tenant-create-success')).toBeInTheDocument()
    })

    expect(screen.getByTestId('tenant-create-success')).toHaveTextContent(
      'Tenant "Bright Future" created',
    )
    expect(screen.getByText('Bright Future')).toBeInTheDocument()
  })

  it('shows create error from API', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTenants,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({ detail: 'A tenant with this slug already exists' }),
      }) as typeof fetch

    render(<TenantsPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-name')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('tenant-name'), 'Apex EduConsult')
    await user.type(screen.getByTestId('tenant-slug'), 'apex')
    await user.type(screen.getByTestId('tenant-owner-email'), 'owner@apex.test')
    await user.click(screen.getByTestId('tenant-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('tenant-create-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('tenant-create-error')).toHaveTextContent(
      'A tenant with this slug already exists',
    )
  })
})
