import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import ForgotPasswordPage from './ForgotPasswordPage'

function renderForgot(initialEntry = '/forgot-password') {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/login" element={<p>Login page</p>} />
          <Route path="/" element={<p>Home page</p>} />
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
    expect(screen.getByRole('link', { name: 'Back to sign in' })).toHaveAttribute('href', '/login')
  })

  it('shows the generic confirmation message after a successful request', async () => {
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

    expect(
      await screen.findByText(/If an account exists for that email, a reset link has been sent./i),
    ).toBeInTheDocument()
    // The form is no longer rendered; the user sees only the confirmation.
    expect(screen.queryByTestId('forgot-submit')).not.toBeInTheDocument()
  })

  it('shows backend error message when the request fails', async () => {
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
    expect(screen.getByTestId('forgot-submit')).toBeInTheDocument()
  })

  it('shows a generic error when the request throws', async () => {
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

  it('shows submitting state while the request is in flight', async () => {
    const user = userEvent.setup()
    let resolveFetch: (value: Response) => void = () => {}
    const fetchPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.endsWith('/auth/forgot-password')) {
          return fetchPromise
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

    resolveFetch({
      ok: true,
      status: 200,
      json: async () => ({ message: 'sent' }),
    } as Response)

    await waitFor(() => {
      expect(submitButton).not.toBeInTheDocument()
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
      expect(screen.getByText('Home page')).toBeInTheDocument()
    })
    expect(screen.queryByRole('heading', { name: 'Forgot password' })).not.toBeInTheDocument()
  })
})