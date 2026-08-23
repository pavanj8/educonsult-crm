import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ReceptionistRoute from './ReceptionistRoute'
import { AuthProvider } from '../store/authStore'

const mockReceptionist = {
  id: 7,
  email: 'receptionist@example.test',
  role: 'receptionist' as const,
  tenant_id: 10,
  branch_id: 1,
}

const mockCounselor = {
  id: 5,
  email: 'counselor@example.test',
  role: 'counselor' as const,
  tenant_id: 10,
  branch_id: 1,
}

function renderRoute(_fetchResponse: unknown) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/receptionist/intake']}>
        <Routes>
          <Route element={<ReceptionistRoute />}>
            <Route
              path="/receptionist/intake"
              element={<p>Intake page</p>}
            />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('ReceptionistRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders the outlet for authenticated receptionist users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockReceptionist,
    }) as typeof fetch

    renderRoute(mockReceptionist)

    await waitFor(() => {
      expect(screen.getByText('Intake page')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('access-denied')).not.toBeInTheDocument()
  })

  it('denies access for non-receptionist users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockCounselor,
    }) as typeof fetch

    renderRoute(mockCounselor)

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })
    expect(screen.queryByText('Intake page')).not.toBeInTheDocument()
  })

  it('denies access for unauthenticated users', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Not authenticated' }),
    }) as typeof fetch

    renderRoute(null)

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })
    expect(screen.queryByText('Intake page')).not.toBeInTheDocument()
  })

  it('shows a loading state while the auth session is being resolved', () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn(
      () =>
        new Promise(() => {
          // never resolves — keeps the auth store in its loading state
        }),
    ) as typeof fetch

    renderRoute(mockReceptionist)

    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(screen.queryByTestId('access-denied')).not.toBeInTheDocument()
    expect(screen.queryByText('Intake page')).not.toBeInTheDocument()
  })
})