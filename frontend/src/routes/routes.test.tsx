import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AppLayout from '../layouts/AppLayout'
import HomePage from '../pages/HomePage'
import NotFoundPage from '../pages/NotFoundPage'
import { AuthProvider } from '../store/authStore'
import ProtectedRoute, { LOGIN_PATH } from './ProtectedRoute'

const mockUser = {
  id: 1,
  email: 'counselor@demo.test',
  role: 'counselor' as const,
  tenant_id: 10,
  branch_id: 1,
}

function TestRouter({ initialPath }: { initialPath: string }) {
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path={LOGIN_PATH} element={<div>Login page</div>} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<HomePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

function renderAt(path: string) {
  return render(
    <AuthProvider>
      <TestRouter initialPath={path} />
    </AuthProvider>,
  )
}

describe('routing shell', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('redirects unauthenticated users to login', async () => {
    renderAt('/')

    await waitFor(() => {
      expect(screen.getByText('Login page')).toBeInTheDocument()
    })
    expect(screen.queryByText('Welcome to EduConsult CRM')).not.toBeInTheDocument()
  })

  it('renders the app layout and home page for authenticated users', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAt('/')

    await waitFor(() => {
      expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    })

    expect(screen.getByRole('heading', { name: 'EduConsult CRM' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('renders the not found page for unknown authenticated routes', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    renderAt('/unknown-route')

    await waitFor(() => {
      expect(screen.getByText('Page not found')).toBeInTheDocument()
    })
  })
})
