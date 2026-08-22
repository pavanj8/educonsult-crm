import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import MasterDataAdminRoute from './MasterDataAdminRoute'

function renderRoute(user: {
  id: number
  email: string
  role: string
  tenant_id: number | null
  branch_id: number | null
}) {
  localStorage.setItem('access_token', 'stored-access-token')
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => user,
  }) as typeof fetch
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/master-data']}>
        <Routes>
          <Route element={<MasterDataAdminRoute />}>
            <Route path="/master-data" element={<p>Master data admin content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('MasterDataAdminRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders for consultancy_owner users', async () => {
    renderRoute({
      id: 50,
      email: 'owner@t.test',
      role: 'consultancy_owner',
      tenant_id: 10,
      branch_id: null,
    })
    await waitFor(() =>
      expect(screen.getByText('Master data admin content')).toBeInTheDocument(),
    )
  })

  it('renders for branch_manager users', async () => {
    renderRoute({
      id: 20,
      email: 'manager@t.test',
      role: 'branch_manager',
      tenant_id: 10,
      branch_id: 1,
    })
    await waitFor(() =>
      expect(screen.getByText('Master data admin content')).toBeInTheDocument(),
    )
  })

  it('denies access to super_admin users (out of scope for tenant-scoped master data)', async () => {
    renderRoute({
      id: 99,
      email: 'admin@t.test',
      role: 'super_admin',
      tenant_id: null,
      branch_id: null,
    })
    await waitFor(() => expect(screen.getByTestId('access-denied')).toBeInTheDocument())
    expect(screen.queryByText('Master data admin content')).not.toBeInTheDocument()
  })

  it('denies access to counselor users', async () => {
    renderRoute({
      id: 1,
      email: 'c@t.test',
      role: 'counselor',
      tenant_id: 10,
      branch_id: 1,
    })
    await waitFor(() => expect(screen.getByTestId('access-denied')).toBeInTheDocument())
    expect(screen.queryByText('Master data admin content')).not.toBeInTheDocument()
  })

  it('denies access to students', async () => {
    renderRoute({
      id: 3,
      email: 's@t.test',
      role: 'student',
      tenant_id: 10,
      branch_id: 1,
    })
    await waitFor(() => expect(screen.getByTestId('access-denied')).toBeInTheDocument())
    expect(screen.queryByText('Master data admin content')).not.toBeInTheDocument()
  })
})