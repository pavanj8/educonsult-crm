import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import LoginPage from './LoginPage'

const mockUser = {
  id: 1,
  email: 'counselor@demo.test',
  role: 'counselor' as const,
  tenant_id: 10,
  branch_id: 1,
}

function mockLoginSuccess() {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          access_token: 'test-access-token',
          refresh_token: 'test-refresh-token',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUser,
      }),
  )
}

function renderLogin() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<p>Welcome to EduConsult CRM</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the sign-in form with required fields', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Not authenticated' }),
      }),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })
    expect(screen.getByTestId('login-email')).toBeInTheDocument()
    expect(screen.getByTestId('login-password')).toBeInTheDocument()
    expect(screen.getByTestId('login-submit')).toBeInTheDocument()
  })

  it('stores tokens and navigates home on successful login', async () => {
    const user = userEvent.setup()
    mockLoginSuccess()

    renderLogin()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    })

    expect(localStorage.getItem('access_token')).toBe('test-access-token')
    expect(localStorage.getItem('refresh_token')).toBe('test-refresh-token')
  })

  it('navigates to the preserved return path after successful login', async () => {
    const user = userEvent.setup()
    mockLoginSuccess()

    render(
      <AuthProvider>
        <MemoryRouter
          initialEntries={[
            {
              pathname: '/login',
              state: { from: { pathname: '/students/42' } },
            },
          ]}
        >
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/students/42" element={<p>Student detail</p>} />
            <Route path="/" element={<p>Welcome to EduConsult CRM</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByText('Student detail')).toBeInTheDocument()
    })
  })

  it('redirects already-authenticated users away from the login page', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockUser,
      }),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    })
    expect(screen.queryByRole('heading', { name: 'Sign in' })).not.toBeInTheDocument()
  })

  it('trims email whitespace before submitting', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ access_token: 'test-access-token', refresh_token: 'test-refresh' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUser,
      })
    vi.stubGlobal('fetch', fetchMock)

    renderLogin()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('login-email'), '  counselor@demo.test  ')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/auth/login',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            email: 'counselor@demo.test',
            password: 'demo-password',
          }),
        }),
      )
    })
  })

  it('shows submitting state while login is in flight', async () => {
    const user = userEvent.setup()
    let resolveLogin: (value: Response) => void = () => {}
    const loginPromise = new Promise<Response>((resolve) => {
      resolveLogin = resolve
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.endsWith('/auth/login')) {
          return loginPromise
        }
        return Promise.resolve({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Not authenticated' }),
        } as Response)
      }),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    const submitButton = screen.getByTestId('login-submit')
    await waitFor(() => {
      expect(submitButton).toBeDisabled()
    })
    expect(submitButton).toHaveTextContent('Signing in…')
    expect(submitButton).toHaveAttribute('aria-busy', 'true')

    resolveLogin({
      ok: true,
      status: 200,
      json: async () => ({ access_token: 'token', refresh_token: 'refresh' }),
    } as Response)

    await waitFor(() => {
      expect(submitButton).not.toBeDisabled()
    })
  })

  it('shows an error message when login fails', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Invalid email or password' }),
      }),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'wrong-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('login-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('login-error')).toHaveTextContent('Invalid email or password')
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(screen.getByTestId('login-email')).toHaveAttribute(
      'aria-describedby',
      screen.getByTestId('login-error').id,
    )
  })

  it('shows a fallback error when validation detail is not a string', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({
          detail: [{ loc: ['body', 'email'], msg: 'field required', type: 'missing' }],
        }),
      }),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('login-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('login-error')).toHaveTextContent('field required')
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('shows a generic error when the login response omits access_token', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({}),
      }),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('login-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('login-error')).toHaveTextContent('Unable to sign in')
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('shows a generic error when the network request fails', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')))

    renderLogin()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('login-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('login-error')).toHaveTextContent('Unable to sign in')
  })

  it('shows server error message for 5xx responses', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({
          detail: 'Authentication service is temporarily unavailable',
        }),
      }),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('login-email'), 'counselor@demo.test')
    await user.type(screen.getByTestId('login-password'), 'demo-password')
    await user.click(screen.getByTestId('login-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('login-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('login-error')).toHaveTextContent(
      'Authentication service is temporarily unavailable',
    )
  })
})
