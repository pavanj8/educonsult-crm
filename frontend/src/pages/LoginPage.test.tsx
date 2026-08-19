import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LoginPage from './LoginPage'

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<p>Welcome to EduConsult CRM</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('renders the sign-in form with required fields', () => {
    renderLogin()

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByTestId('login-email')).toBeInTheDocument()
    expect(screen.getByTestId('login-password')).toBeInTheDocument()
    expect(screen.getByTestId('login-submit')).toBeInTheDocument()
  })

  it('stores tokens and navigates home on successful login', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
      }),
    }) as typeof fetch

    renderLogin()

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    })

    expect(localStorage.getItem('access_token')).toBe('test-access-token')
    expect(localStorage.getItem('refresh_token')).toBe('test-refresh-token')
    expect(globalThis.fetch).toHaveBeenCalledWith('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'counselor@demo.test',
        password: 'demo-password',
      }),
    })
  })

  it('shows an error message when login fails', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Invalid email or password' }),
    }) as typeof fetch

    renderLogin()

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'wrong-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('login-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('login-error')).toHaveTextContent('Invalid email or password')
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('shows a generic error when the network request fails', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Network error')) as typeof fetch

    renderLogin()

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('login-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('login-error')).toHaveTextContent('Unable to sign in')
  })
})
