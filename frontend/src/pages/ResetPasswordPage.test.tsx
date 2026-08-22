import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import ResetPasswordPage from './ResetPasswordPage'

const VALID_TOKEN = 'valid-reset-token'

function renderReset(initialPath: string = `/reset-password?token=${VALID_TOKEN}`) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<p>Login page</p>} />
          <Route path="/" element={<p>Welcome to EduConsult CRM</p>} />
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

  it('renders the new password and confirm password fields when a token is present', async () => {
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
  })

  it('submits token + new password to /auth/reset-password', async () => {
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
          body: JSON.stringify({
            token: VALID_TOKEN,
            new_password: 'new-strong-password',
          }),
        }),
      )
    })
  })

  it('shows a confirmation message after a successful reset', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ message: 'Your password has been reset successfully.' }),
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
      expect(screen.getByText('Your password has been reset successfully.')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('reset-password')).not.toBeInTheDocument()
    expect(screen.queryByTestId('reset-submit')).not.toBeInTheDocument()
  })

  it('shows an error when the backend rejects the token with 400', async () => {
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
  })

  it('shows a mismatch error when the two password fields do not match', async () => {
    const user = userEvent.setup()
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

    await user.type(screen.getByTestId('reset-password'), 'new-strong-password')
    await user.type(screen.getByTestId('reset-password-confirm'), 'different-password')
    await user.click(screen.getByTestId('reset-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('reset-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('reset-error')).toHaveTextContent('Passwords do not match')
  })

  it('disables the form and shows a missing-token message when no token is in the URL', async () => {
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
      'Reset link is missing or invalid. Please request a new password reset email.',
    )
    expect(screen.getByTestId('reset-submit')).toBeDisabled()
    expect(screen.getByTestId('reset-password')).toBeDisabled()
    expect(screen.getByTestId('reset-password-confirm')).toBeDisabled()
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
        if (url.endsWith('/auth/reset-password')) {
          return requestPromise
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

    resolveRequest({
      ok: true,
      status: 200,
      json: async () => ({ message: 'Your password has been reset successfully.' }),
    } as Response)

    await waitFor(() => {
      expect(screen.getByText('Your password has been reset successfully.')).toBeInTheDocument()
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
      expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('heading', { name: 'Choose a new password' }),
    ).not.toBeInTheDocument()
  })
})
