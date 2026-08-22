import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import ForgotPasswordPage from './ForgotPasswordPage'

function renderForgot(initialEntries: string[] = ['/forgot-password']) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/login" element={<p>Login page</p>} />
          <Route path="/" element={<p>Welcome to EduConsult CRM</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the email field and submit button', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Not authenticated' }),
      }),
    )

    renderForgot()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Forgot password' })).toBeInTheDocument()
    })
    expect(screen.getByTestId('forgot-email')).toBeInTheDocument()
    expect(screen.getByTestId('forgot-submit')).toBeInTheDocument()
  })

  it('submits the email to /auth/forgot-password on send', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        message: 'If an account exists for that email, a reset link has been sent.',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderForgot()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Forgot password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('forgot-email'), 'counselor@demo.test')
    await user.click(screen.getByTestId('forgot-submit'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/auth/forgot-password',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'counselor@demo.test' }),
        }),
      )
    })
  })

  it('trims whitespace from the email before submitting', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        message: 'If an account exists for that email, a reset link has been sent.',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderForgot()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Forgot password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('forgot-email'), '  counselor@demo.test  ')
    await user.click(screen.getByTestId('forgot-submit'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/auth/forgot-password',
        expect.objectContaining({
          body: JSON.stringify({ email: 'counselor@demo.test' }),
        }),
      )
    })
  })

  it('shows a confirmation message after a successful submission', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          message: 'If an account exists for that email, a reset link has been sent.',
        }),
      }),
    )

    renderForgot()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Forgot password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('forgot-email'), 'counselor@demo.test')
    await user.click(screen.getByTestId('forgot-submit'))

    await waitFor(() => {
      expect(
        screen.getByText(/If an account exists for that email, a reset link has been sent\./i),
      ).toBeInTheDocument()
    })
    expect(screen.queryByTestId('forgot-email')).not.toBeInTheDocument()
    expect(screen.queryByTestId('forgot-submit')).not.toBeInTheDocument()
  })

  it('shows an error message when the backend returns a 503 delivery failure', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'Unable to send password reset email' }),
      }),
    )

    renderForgot()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Forgot password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('forgot-email'), 'counselor@demo.test')
    await user.click(screen.getByTestId('forgot-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('forgot-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('forgot-error')).toHaveTextContent(
      'Unable to send password reset email',
    )
  })

  it('shows a fallback error when the network request fails', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')))

    renderForgot()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Forgot password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('forgot-email'), 'counselor@demo.test')
    await user.click(screen.getByTestId('forgot-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('forgot-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('forgot-error')).toHaveTextContent('Unable to send reset email')
  })

  it('shows submitting state while the reset request is in flight', async () => {
    const user = userEvent.setup()
    let resolveRequest: (value: Response) => void = () => {}
    const requestPromise = new Promise<Response>((resolve) => {
      resolveRequest = resolve
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.endsWith('/auth/forgot-password')) {
          return requestPromise
        }
        return Promise.resolve({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Not authenticated' }),
        } as Response)
      }),
    )

    renderForgot()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Forgot password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('forgot-email'), 'counselor@demo.test')
    await user.click(screen.getByTestId('forgot-submit'))

    const submitButton = screen.getByTestId('forgot-submit')
    await waitFor(() => {
      expect(submitButton).toBeDisabled()
    })
    expect(submitButton).toHaveTextContent('Sending…')
    expect(submitButton).toHaveAttribute('aria-busy', 'true')

    resolveRequest({
      ok: true,
      status: 200,
      json: async () => ({ message: 'ok' }),
    } as Response)

    await waitFor(() => {
      expect(
        screen.getByText(/If an account exists for that email, a reset link has been sent\./i),
      ).toBeInTheDocument()
    })
  })

  it('redirects already-authenticated users to the home page', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          id: 1,
          email: 'counselor@demo.test',
          role: 'counselor',
          tenant_id: 10,
          branch_id: 1,
        }),
      }),
    )

    renderForgot()

    await waitFor(() => {
      expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    })
    expect(screen.queryByRole('heading', { name: 'Forgot password' })).not.toBeInTheDocument()
  })

  it('renders a link back to the login page', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Not authenticated' }),
      }),
    )

    renderForgot()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Forgot password' })).toBeInTheDocument()
    })

    expect(screen.getByRole('link', { name: /Back to sign in/i })).toHaveAttribute('href', '/login')
  })
})
