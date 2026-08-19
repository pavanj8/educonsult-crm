import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import SuperAdminRoute from './SuperAdminRoute'

function renderSuperAdminRoute(user: {
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
      <MemoryRouter initialEntries={['/tenants']}>
        <Routes>
          <Route element={<SuperAdminRoute />}>
            <Route path="/tenants" element={<p>Super admin content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('SuperAdminRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders child routes for super admin users', async () => {
    renderSuperAdminRoute({
      id: 1,
      email: 'super_admin@demo.test',
      role: 'super_admin',
      tenant_id: null,
      branch_id: null,
    })

    await waitFor(() => {
      expect(screen.getByText('Super admin content')).toBeInTheDocument()
    })
  })

  it('shows access denied for non-super-admin users', async () => {
    renderSuperAdminRoute({
      id: 2,
      email: 'counselor@demo.test',
      role: 'counselor',
      tenant_id: 10,
      branch_id: 1,
    })

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })

    expect(screen.queryByText('Super admin content')).not.toBeInTheDocument()
  })
})
