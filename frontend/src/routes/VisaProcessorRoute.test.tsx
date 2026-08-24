import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import VisaProcessorRoute from './VisaProcessorRoute'

function renderVisaProcessorRoute(user: {
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
      <MemoryRouter initialEntries={['/visa']}>
        <Routes>
          <Route element={<VisaProcessorRoute />}>
            <Route path="/visa" element={<p>Visa processor dashboard content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('VisaProcessorRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders child routes for visa processor users', async () => {
    renderVisaProcessorRoute({
      id: 91,
      email: 'visa@demo.test',
      role: 'visa_processor',
      tenant_id: 10,
      branch_id: null,
    })

    await waitFor(() => {
      expect(screen.getByText('Visa processor dashboard content')).toBeInTheDocument()
    })
  })

  it('shows access denied for non-visa-processor users', async () => {
    renderVisaProcessorRoute({
      id: 2,
      email: 'counselor@demo.test',
      role: 'counselor',
      tenant_id: 10,
      branch_id: 1,
    })

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })
    expect(screen.queryByText('Visa processor dashboard content')).not.toBeInTheDocument()
  })
})
