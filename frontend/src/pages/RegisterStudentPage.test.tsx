import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import { REGISTER_PATH } from '../routes/paths'
import RegisterStudentPage from './RegisterStudentPage'

const mockStudentUser = {
  id: 42,
  email: 'new.student@example.test',
  role: 'student' as const,
  tenant_id: 10,
  branch_id: 1,
}

const mockRegisterResponse = {
  id: 42,
  email: 'new.student@example.test',
  role: 'student',
  tenant_id: 10,
  branch_id: 1,
  name: 'Rahul Kumar',
  phone: '+91-9876543210',
  date_of_birth: '2000-05-15',
  target_country_id: null,
  target_university_id: null,
  target_program_id: null,
  access_token: 'test-access-token',
  refresh_token: 'test-refresh-token',
  token_type: 'bearer',
  created_at: '2026-01-01T00:00:00Z',
}

function mockRegisterSuccess() {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockRegisterResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockStudentUser,
      }),
  )
}

function renderRegister(initialEntry = REGISTER_PATH) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path={REGISTER_PATH} element={<RegisterStudentPage />} />
          <Route path="/" element={<p>Welcome to EduConsult CRM</p>} />
          <Route path="/login" element={<p>Sign in page</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

async function fillRegisterForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByTestId('register-tenant-slug'), 'apex')
  await user.type(screen.getByTestId('register-branch-id'), '1')
  await user.type(screen.getByTestId('register-name'), 'Rahul Kumar')
  await user.type(screen.getByTestId('register-email'), 'new.student@example.test')
  await user.type(screen.getByTestId('register-password'), 'StudentPass1!')
  await user.type(screen.getByTestId('register-phone'), '+91-9876543210')
  await user.type(screen.getByTestId('register-date-of-birth'), '2000-05-15')
}

describe('RegisterStudentPage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the registration form with required fields', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Not authenticated' }),
      }),
    )

    renderRegister()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create student account' })).toBeInTheDocument()
    })

    expect(screen.getByTestId('register-tenant-slug')).toBeInTheDocument()
    expect(screen.getByTestId('register-branch-id')).toBeInTheDocument()
    expect(screen.getByTestId('register-name')).toBeInTheDocument()
    expect(screen.getByTestId('register-email')).toBeInTheDocument()
    expect(screen.getByTestId('register-password')).toBeInTheDocument()
    expect(screen.getByTestId('register-phone')).toBeInTheDocument()
    expect(screen.getByTestId('register-date-of-birth')).toBeInTheDocument()
    expect(screen.getByTestId('register-submit')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })

  it('stores tokens and navigates home on successful registration', async () => {
    const user = userEvent.setup()
    mockRegisterSuccess()

    renderRegister()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create student account' })).toBeInTheDocument()
    })

    await fillRegisterForm(user)
    await user.click(screen.getByTestId('register-submit'))

    await waitFor(() => {
      expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    })

    expect(localStorage.getItem('access_token')).toBe('test-access-token')
    expect(localStorage.getItem('refresh_token')).toBe('test-refresh-token')
  })

  it('submits trimmed profile fields to the registration API', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockRegisterResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockStudentUser,
      })
    vi.stubGlobal('fetch', fetchMock)

    renderRegister()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create student account' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('register-tenant-slug'), '  apex  ')
    await user.type(screen.getByTestId('register-branch-id'), '1')
    await user.type(screen.getByTestId('register-name'), '  Rahul Kumar  ')
    await user.type(screen.getByTestId('register-email'), '  new.student@example.test  ')
    await user.type(screen.getByTestId('register-password'), 'StudentPass1!')
    await user.type(screen.getByTestId('register-phone'), '  +91-9876543210  ')
    await user.type(screen.getByTestId('register-date-of-birth'), '2000-05-15')
    await user.click(screen.getByTestId('register-submit'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/auth/register-student',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            tenant_slug: 'apex',
            branch_id: 1,
            name: 'Rahul Kumar',
            email: 'new.student@example.test',
            password: 'StudentPass1!',
            phone: '+91-9876543210',
            date_of_birth: '2000-05-15',
          }),
        }),
      )
    })
  })

  it('shows submitting state while registration is in flight', async () => {
    const user = userEvent.setup()
    let resolveRegister: (value: Response) => void = () => {}
    const registerPromise = new Promise<Response>((resolve) => {
      resolveRegister = resolve
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.endsWith('/auth/register-student')) {
          return registerPromise
        }
        return Promise.resolve({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Not authenticated' }),
        } as Response)
      }),
    )

    renderRegister()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create student account' })).toBeInTheDocument()
    })

    await fillRegisterForm(user)
    await user.click(screen.getByTestId('register-submit'))

    const submitButton = screen.getByTestId('register-submit')
    await waitFor(() => {
      expect(submitButton).toBeDisabled()
    })
    expect(submitButton).toHaveTextContent('Creating account…')
    expect(submitButton).toHaveAttribute('aria-busy', 'true')

    resolveRegister({
      ok: true,
      status: 201,
      json: async () => mockRegisterResponse,
    } as Response)

    await waitFor(() => {
      expect(submitButton).not.toBeDisabled()
    })
  })

  it('shows an error message when registration fails', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ detail: 'Email already registered' }),
      }),
    )

    renderRegister()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create student account' })).toBeInTheDocument()
    })

    await fillRegisterForm(user)
    await user.click(screen.getByTestId('register-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('register-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('register-error')).toHaveTextContent('Email already registered')
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('shows a client-side error for invalid branch ID', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    renderRegister()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create student account' })).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('register-tenant-slug'), 'apex')
    await user.type(screen.getByTestId('register-branch-id'), 'abc')
    await user.type(screen.getByTestId('register-name'), 'Rahul Kumar')
    await user.type(screen.getByTestId('register-email'), 'new.student@example.test')
    await user.type(screen.getByTestId('register-password'), 'StudentPass1!')
    await user.type(screen.getByTestId('register-phone'), '+91-9876543210')
    await user.type(screen.getByTestId('register-date-of-birth'), '2000-05-15')
    fireEvent.submit(screen.getByTestId('register-submit').closest('form')!)

    await waitFor(() => {
      expect(screen.getByTestId('register-error')).toHaveTextContent(
        'Branch ID must be a positive number',
      )
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('redirects already-authenticated users away from the registration page', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockStudentUser,
      }),
    )

    renderRegister()

    await waitFor(() => {
      expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('heading', { name: 'Create student account' }),
    ).not.toBeInTheDocument()
  })

  it('shows a generic error when the network request fails', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')))

    renderRegister()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create student account' })).toBeInTheDocument()
    })

    await fillRegisterForm(user)
    await user.click(screen.getByTestId('register-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('register-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('register-error')).toHaveTextContent('Unable to create account')
  })
})
