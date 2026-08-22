import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import ResetPasswordPage from './ResetPasswordPage'

const VALID_TOKEN = 'valid-reset-token'

function renderReset(initialEntry?: string) {
  const entry = initialEntry ?? `/reset-password?token=${VALID_TOKEN}`
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<p>Login page</p>} />
          <Route path="/" element={<p>Home page</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the new-password and confirm fields and pre-reads the token from the query string', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Not authenticated' }),
      }),
    )

    renderReset()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument()
    })
    expect(screen.getByTestId('reset-password')).toBeInTheDocument()
    expect(screen.getByTestId('reset-password-confirm')).toBeInTheDocument()
    expect(screen.getByTestId('reset-submit')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to sign in' })).toHaveAttribute('href', '/login')
  })

  it('submits the new password with the token and shows the success screen', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'Your password has been reset successfully.' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderReset()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('reset-password'), 'new-strong-password')
    await user.type(screen.getByTestId('reset-password-confirm'), 'new-strong-password')
    await user.click(screen.getByTestId('reset-submit'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/auth/reset-password',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ token: VALID_TOKEN, new_password: 'new-strong-password' }),
        }),
      )
    })

    expect(
      await screen.findByText(/Your password has been reset successfully./i),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('reset-submit')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Sign in with your new password/i })).toHaveAttribute(
      'href',
      '/login',
    )
  })

  it('shows backend error for an invalid or expired token', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Invalid or expired reset token' }),
      }),
    )

    renderReset()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('reset-password'), 'new-strong-password')
    await user.type(screen.getByTestId('reset-password-confirm'), 'new-strong-password')
    await user.click(screen.getByTestId('reset-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('reset-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('reset-error')).toHaveTextContent('Invalid or expired reset token')
    // Form is still rendered so the user can retry (e.g. after requesting a fresh email).
    expect(screen.getByTestId('reset-submit')).toBeInTheDocument()
  })

  it('rejects mismatched passwords before calling the backend', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Not authenticated' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderReset()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('reset-password'), 'new-strong-password')
    await user.type(screen.getByTestId('reset-password-confirm'), 'different-password')
    await user.click(screen.getByTestId('reset-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('reset-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('reset-error')).toHaveTextContent('Passwords do not match')
    expect(fetchMock).not.toHaveBeenCalledWith(
      '/auth/reset-password',
      expect.anything(),
    )
  })

  it('shows an error when the token query parameter is missing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Not authenticated' }),
      }),
    )

    renderReset('/reset-password')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument()
    })

    expect(screen.getByTestId('reset-error')).toHaveTextContent(
      'Reset link is missing or invalid',
    )
    expect(screen.getByTestId('reset-submit')).toBeDisabled()
    expect(screen.getByTestId('reset-password')).toBeDisabled()
  })

  it('shows a generic error when the network request throws', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')))

    renderReset()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('reset-password'), 'new-strong-password')
    await user.type(screen.getByTestId('reset-password-confirm'), 'new-strong-password')
    await user.click(screen.getByTestId('reset-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('reset-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('reset-error')).toHaveTextContent('Unable to reset password')
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
        if (url.endsWith('/auth/reset-password')) {
          return fetchPromise
        }
        return Promise.resolve({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Not authenticated' }),
        } as Response)
      }),
    )

    renderReset()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('reset-password'), 'new-strong-password')
    await user.type(screen.getByTestId('reset-password-confirm'), 'new-strong-password')
    await user.click(screen.getByTestId('reset-submit'))

    const submitButton = screen.getByTestId('reset-submit')
    await waitFor(() => {
      expect(submitButton).toBeDisabled()
    })
    expect(submitButton).toHaveTextContent('Resetting…')
    expect(submitButton).toHaveAttribute('aria-busy', 'true')

    resolveFetch({
      ok: true,
      status: 200,
      json: async () => ({ message: 'Your password has been reset successfully.' }),
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

    renderReset()

    await waitFor(() => {
      expect(screen.getByText('Home page')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('heading', { name: 'Choose a new password' }),
    ).not.toBeInTheDocument()
  })
})