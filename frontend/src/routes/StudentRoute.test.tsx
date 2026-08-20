import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import StudentRoute from './StudentRoute'

function renderStudentRoute(user: {
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
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route element={<StudentRoute />}>
            <Route path="/dashboard" element={<p>Student dashboard content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('StudentRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders child routes for student users', async () => {
    renderStudentRoute({
      id: 8,
      email: 'student@demo.test',
      role: 'student',
      tenant_id: 10,
      branch_id: 1,
    })

    await waitFor(() => {
      expect(screen.getByText('Student dashboard content')).toBeInTheDocument()
    })
  })

  it('shows access denied for non-student users', async () => {
    renderStudentRoute({
      id: 2,
      email: 'counselor@demo.test',
      role: 'counselor',
      tenant_id: 10,
      branch_id: 1,
    })

    await waitFor(() => {
      expect(screen.getByTestId('access-denied')).toBeInTheDocument()
    })

    expect(screen.queryByText('Student dashboard content')).not.toBeInTheDocument()
  })
})
