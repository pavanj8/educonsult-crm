import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import VerifierRoute from './VerifierRoute'

function renderVerifierRoute(user: {
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
      <MemoryRouter initialEntries={['/verifier']}>
        <Routes>
          <Route element={<VerifierRoute />}>
            <Route path="/verifier" element={<p>Verifier dashboard content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('VerifierRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders child routes for document verifier users', async () => {
    renderVerifierRoute({
      id: 90,
      email: 'verifier@demo.test',
      role: 'document_verifier',
      tenant_id: 10,
      branch_id: null,
    })

    await waitFor(() => {
      expect(screen.getByText('Verifier dashboard content')).toBeInTheDocument()
    })
  })

  it('shows access denied for non-verifier users', async () => {
    renderVerifierRoute({
      id: 2,
      email: 'counselor@demo.test',
      role: 'counselor',
      tenant_id: 10,
      branch_id: 1,
    })

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })
    expect(screen.queryByText('Verifier dashboard content')).not.toBeInTheDocument()
  })
})
