import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProtectedRoute, { LOGIN_PATH } from './ProtectedRoute'
import { LANDING_PATH } from './paths'

const mockUseAuth = vi.fn()

vi.mock('../store/authStore', () => ({
  useAuth: () => mockUseAuth(),
}))

function renderProtected(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path={LOGIN_PATH} element={<div>Login page</div>} />
        <Route path={LANDING_PATH} element={<div>Landing page</div>} />
        <Route element={<ProtectedRoute />}>
          <Route index element={<div>Protected content</div>} />
          <Route path="staff" element={<div>Protected content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    mockUseAuth.mockReset()
  })

  it('shows loading state while auth is being resolved', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
    })

    renderProtected()

    expect(screen.getByRole('status', { name: 'Loading' })).toHaveTextContent('Loading…')
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
    expect(screen.queryByText('Login page')).not.toBeInTheDocument()
  })

  it('sends an unauthenticated visitor at the bare root to the landing page', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
    })

    renderProtected('/')

    // Typing the bare URL is a visit, not a bounced deep link -- the marketing
    // page is the entry point, and the login form is one click on from there.
    expect(screen.getByText('Landing page')).toBeInTheDocument()
    expect(screen.queryByText('Login page')).not.toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
  })

  it('redirects unauthenticated users from a protected deep link to login', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
    })

    renderProtected('/staff')

    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Landing page')).not.toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
  })

  it('renders protected content for authenticated users', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
    })

    renderProtected()

    expect(screen.getByText('Protected content')).toBeInTheDocument()
    expect(screen.queryByText('Login page')).not.toBeInTheDocument()
  })
})
