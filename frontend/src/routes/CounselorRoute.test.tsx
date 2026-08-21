import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import CounselorRoute from './CounselorRoute'

function renderRoute(user: { id: number; email: string; role: string; tenant_id: number | null; branch_id: number | null }) {
  localStorage.setItem('access_token', 'stored-access-token')
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => user }) as typeof fetch
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/my-applications']}>
        <Routes>
          <Route element={<CounselorRoute />}>
            <Route path="/my-applications" element={<p>Counselor queue content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('CounselorRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders for counselor users', async () => {
    renderRoute({ id: 1, email: 'c@t.test', role: 'counselor', tenant_id: 10, branch_id: 1 })
    await waitFor(() => expect(screen.getByText('Counselor queue content')).toBeInTheDocument())
  })

  it('renders for branch_manager users', async () => {
    renderRoute({ id: 2, email: 'm@t.test', role: 'branch_manager', tenant_id: 10, branch_id: 1 })
    await waitFor(() => expect(screen.getByText('Counselor queue content')).toBeInTheDocument())
  })

  it('denies access to students', async () => {
    renderRoute({ id: 3, email: 's@t.test', role: 'student', tenant_id: 10, branch_id: 1 })
    await waitFor(() => expect(screen.getByTestId('access-denied')).toBeInTheDocument())
    expect(screen.queryByText('Counselor queue content')).not.toBeInTheDocument()
  })
})
