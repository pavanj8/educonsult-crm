import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ReceptionistIntakePage from './ReceptionistIntakePage'
import { AuthProvider } from '../store/authStore'
import { BrandingProvider } from '../store/brandingStore'
import { RECEPTIONIST_INTAKE_PATH } from '../routes/paths'
import type { AuthUser } from '../types/auth'

const mockReceptionist: AuthUser = {
  id: 7,
  email: 'receptionist@example.test',
  role: 'receptionist',
  tenant_id: 10,
  branch_id: 1,
}

const mockIntakeResponse = {
  id: 99,
  email: 'walkin.student@example.test',
  role: 'student' as const,
  tenant_id: 10,
  branch_id: 1,
  name: 'Aarav Sharma',
  phone: '+91-9876543210',
  date_of_birth: '2001-03-04',
  target_country_id: null,
  target_university_id: null,
  target_program_id: null,
  created_at: '2026-01-01T00:00:00Z',
}

const mockCountries = [{ id: 1, tenant_id: 10, name: 'Canada', code: 'CA' }]
const mockUniversities = [{ id: 10, tenant_id: 10, country_id: 1, name: 'University of Toronto' }]
const mockPrograms = [{ id: 100, tenant_id: 10, university_id: 10, name: 'Computer Science MSc' }]

const mockTenant = {
  id: 10,
  name: 'Apex Consultancy',
  slug: 'apex',
  logo_url: null,
  brand_color: null,
  currency: 'INR',
}

// Password meets the platform strong-password policy (uppercase + lowercase
// + digit + special, >= 8 chars; see backend/app/auth/password_policy.py).
const TEMPORARY_PASSWORD = 'Welcome1!'

type IntakeHandler = (url: string, init?: RequestInit) => Response | Promise<Response>
type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response>

function buildFetchMock(options: {
  intake: IntakeHandler
}): FetchHandler {
  return (url: string, init?: RequestInit) => {
    if (url.endsWith('/students') && init?.method === 'POST') {
      return options.intake(url, init)
    }
    if (url.endsWith('/tenants/10')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => mockTenant,
      } as Response)
    }
    if (url.endsWith('/tenants/apex/countries')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => mockCountries,
      } as Response)
    }
    if (url.endsWith('/tenants/apex/universities?country_id=1')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => mockUniversities,
      } as Response)
    }
    if (url.endsWith('/tenants/apex/programs?university_id=10')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => mockPrograms,
      } as Response)
    }
    return Promise.resolve({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Not found' }),
    } as Response)
  }
}

function renderIntake(options: {
  intake?: IntakeHandler
  user?: typeof mockReceptionist
} = {}) {
  localStorage.setItem('access_token', 'test-access-token')
  localStorage.setItem('refresh_token', 'test-refresh-token')
  const user = options.user ?? mockReceptionist

  let capturedIntake: { url: string; init?: RequestInit } | null = null

  const intakeHandler: IntakeHandler = options.intake
    ? (url, init) => {
        capturedIntake = { url, init }
        return options.intake!(url, init)
      }
    : () =>
        Promise.resolve({
          ok: false,
          status: 404,
          json: async () => ({ detail: 'Not found' }),
        } as Response)

  const fetchMock = vi.fn(buildFetchMock({ intake: intakeHandler }))

  // /auth/me resolves to the receptionist user so the AuthProvider
  // hydrates the user record and exposes branch_id to the page.
  const wrappedFetch = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith('/auth/me')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => user,
      } as Response)
    }
    return fetchMock(url, init)
  })

  globalThis.fetch = wrappedFetch as typeof fetch

  const view = render(
    <AuthProvider>
      <BrandingProvider>
        <MemoryRouter initialEntries={[RECEPTIONIST_INTAKE_PATH]}>
          <Routes>
            <Route
              path={RECEPTIONIST_INTAKE_PATH}
              element={<ReceptionistIntakePage />}
            />
          </Routes>
        </MemoryRouter>
      </BrandingProvider>
    </AuthProvider>,
  )

  return { ...view, capturedIntake: () => capturedIntake, fetchMock }
}

async function fillProfile(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByTestId('receptionist-intake-name'), 'Aarav Sharma')
  await user.type(
    screen.getByTestId('receptionist-intake-email'),
    'walkin.student@example.test',
  )
  await user.type(screen.getByTestId('receptionist-intake-password'), TEMPORARY_PASSWORD)
  await user.type(screen.getByTestId('receptionist-intake-phone'), '+91-9876543210')
  await user.type(screen.getByTestId('receptionist-intake-date-of-birth'), '2001-03-04')
}

describe('ReceptionistIntakePage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the intake form with profile fields and study-preferences dropdowns', async () => {
    renderIntake()

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    expect(screen.getByTestId('receptionist-intake-branch-note')).toHaveTextContent(
      'branch 1',
    )
    expect(screen.getByTestId('receptionist-intake-name')).toBeInTheDocument()
    expect(screen.getByTestId('receptionist-intake-email')).toBeInTheDocument()
    expect(screen.getByTestId('receptionist-intake-password')).toBeInTheDocument()
    expect(screen.getByTestId('receptionist-intake-phone')).toBeInTheDocument()
    expect(screen.getByTestId('receptionist-intake-date-of-birth')).toBeInTheDocument()
    expect(screen.getByTestId('intake-target-country')).toBeInTheDocument()
    expect(screen.getByTestId('intake-target-university')).toBeInTheDocument()
    expect(screen.getByTestId('intake-target-program')).toBeInTheDocument()
    expect(screen.getByTestId('receptionist-intake-submit')).toBeInTheDocument()
  })

  it('submits the receptionist branch and required profile fields (including a temporary password) to /students', async () => {
    const user = userEvent.setup()
    const { capturedIntake } = renderIntake({
      intake: async () =>
        ({
          ok: true,
          status: 201,
          json: async () => mockIntakeResponse,
        }) as Response,
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    await fillProfile(user)
    await user.click(screen.getByTestId('receptionist-intake-submit'))

    await waitFor(() => {
      expect(capturedIntake()).not.toBeNull()
    })

    const captured = capturedIntake()
    expect(captured?.url).toBe('/students')
    expect(captured?.init?.method).toBe('POST')
    // The backend's StaffCreateStudentRequest schema requires a `password`
    // (min 8 chars, strong policy); the receptionist intake form must
    // therefore send the temporary password the receptionist types in.
    expect(JSON.parse(String(captured?.init?.body))).toEqual({
      branch_id: 1,
      name: 'Aarav Sharma',
      email: 'walkin.student@example.test',
      password: TEMPORARY_PASSWORD,
      phone: '+91-9876543210',
      date_of_birth: '2001-03-04',
    })

    await waitFor(() => {
      expect(screen.getByTestId('receptionist-intake-success')).toBeInTheDocument()
    })
    expect(screen.getByTestId('receptionist-intake-success')).toHaveTextContent(
      'walkin.student@example.test',
    )
  })

  it('includes the selected study-preference ids in the /students payload', async () => {
    const user = userEvent.setup()
    const { capturedIntake } = renderIntake({
      intake: async () =>
        ({
          ok: true,
          status: 201,
          json: async () => ({
            ...mockIntakeResponse,
            target_country_id: 1,
            target_university_id: 10,
            target_program_id: 100,
          }),
        }) as Response,
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Canada' })).toBeInTheDocument()
    })
    await user.selectOptions(screen.getByTestId('intake-target-country'), '1')
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'University of Toronto' })).toBeInTheDocument()
    })
    await user.selectOptions(screen.getByTestId('intake-target-university'), '10')
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Computer Science MSc' })).toBeInTheDocument()
    })
    await user.selectOptions(screen.getByTestId('intake-target-program'), '100')

    await fillProfile(user)
    await user.click(screen.getByTestId('receptionist-intake-submit'))

    await waitFor(() => {
      expect(capturedIntake()).not.toBeNull()
    })

    expect(JSON.parse(String(capturedIntake()?.init?.body))).toEqual({
      branch_id: 1,
      name: 'Aarav Sharma',
      email: 'walkin.student@example.test',
      password: TEMPORARY_PASSWORD,
      phone: '+91-9876543210',
      date_of_birth: '2001-03-04',
      target_country_id: 1,
      target_university_id: 10,
      target_program_id: 100,
    })
  })

  it('shows an error message when /students returns a backend error', async () => {
    const user = userEvent.setup()
    renderIntake({
      intake: async () =>
        ({
          ok: false,
          status: 409,
          json: async () => ({ detail: 'Email already registered' }),
        }) as Response,
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    await fillProfile(user)
    await user.click(screen.getByTestId('receptionist-intake-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('receptionist-intake-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('receptionist-intake-error')).toHaveTextContent(
      'Email already registered',
    )
    expect(screen.queryByTestId('receptionist-intake-success')).not.toBeInTheDocument()
  })

  it('surfaces the backend validation message when /students rejects a 422 for a missing required field', async () => {
    // Mirrors the backend's `StaffCreateStudentRequest` Pydantic validation
    // response shape (`detail` is an array of {loc, msg, type} entries).
    const user = userEvent.setup()
    renderIntake({
      intake: async () =>
        ({
          ok: false,
          status: 422,
          json: async () => ({
            detail: [
              {
                loc: ['body', 'name'],
                msg: 'Field required',
                type: 'value_error.missing',
              },
            ],
          }),
        }) as Response,
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    // Fill the profile including the temporary password — the form
    // itself considers the request well-formed (the backend is the one
    // rejecting it). This proves the error UX is wired to the API's
    // 422 response and not just to client-side validation.
    await fillProfile(user)
    await user.click(screen.getByTestId('receptionist-intake-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('receptionist-intake-error')).toBeInTheDocument()
    })
    // apiFetch's parseErrorMessage surfaces the first entry's `msg` for
    // FastAPI's array-shaped validation errors.
    expect(screen.getByTestId('receptionist-intake-error')).toHaveTextContent(
      'Field required',
    )
    expect(screen.queryByTestId('receptionist-intake-success')).not.toBeInTheDocument()
  })

  it('disables the submit button and shows submitting state while the request is in flight', async () => {
    const user = userEvent.setup()
    let resolveIntake: (value: Response) => void = () => {}
    const intakePromise = new Promise<Response>((resolve) => {
      resolveIntake = resolve
    })

    renderIntake({
      intake: async () => intakePromise,
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    await fillProfile(user)
    await user.click(screen.getByTestId('receptionist-intake-submit'))

    const submitButton = screen.getByTestId('receptionist-intake-submit')
    await waitFor(() => {
      expect(submitButton).toBeDisabled()
    })
    expect(submitButton).toHaveTextContent('Registering…')
    expect(submitButton).toHaveAttribute('aria-busy', 'true')

    resolveIntake({
      ok: true,
      status: 201,
      json: async () => mockIntakeResponse,
    } as Response)

    await waitFor(() => {
      expect(submitButton).not.toBeDisabled()
    })
  })

  it('resets the form after a successful intake so the receptionist can register another student', async () => {
    const user = userEvent.setup()
    renderIntake({
      intake: async () =>
        ({
          ok: true,
          status: 201,
          json: async () => mockIntakeResponse,
        }) as Response,
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    await fillProfile(user)
    await user.click(screen.getByTestId('receptionist-intake-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('receptionist-intake-success')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByTestId('receptionist-intake-name')).toHaveValue('')
    })
    expect(screen.getByTestId('receptionist-intake-email')).toHaveValue('')
    expect(screen.getByTestId('receptionist-intake-password')).toHaveValue('')
    expect(screen.getByTestId('receptionist-intake-phone')).toHaveValue('')
    expect(screen.getByTestId('receptionist-intake-date-of-birth')).toHaveValue('')
    expect(screen.getByTestId('receptionist-intake-success')).toHaveTextContent(
      'walkin.student@example.test',
    )
  })

  it('displays the temporary password on the success banner so the receptionist can hand it to the walk-in', async () => {
    const user = userEvent.setup()
    renderIntake({
      intake: async () =>
        ({
          ok: true,
          status: 201,
          json: async () => mockIntakeResponse,
        }) as Response,
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    await fillProfile(user)
    await user.click(screen.getByTestId('receptionist-intake-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('receptionist-intake-issued-password')).toBeInTheDocument()
    })
    expect(screen.getByTestId('receptionist-intake-issued-password')).toHaveTextContent(
      TEMPORARY_PASSWORD,
    )
  })

  it('shows a generic error message when the network request throws', async () => {
    const user = userEvent.setup()

    renderIntake({
      intake: async () => {
        throw new Error('Network error')
      },
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    await fillProfile(user)
    await user.click(screen.getByTestId('receptionist-intake-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('receptionist-intake-error')).toHaveTextContent(
        'Unable to register student',
      )
    })
  })

  it('disables the submit button and shows a branch-missing note when the receptionist has no branch assigned', async () => {
    renderIntake({ user: { ...mockReceptionist, branch_id: null } })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New student intake' }),
      ).toBeInTheDocument()
    })

    expect(screen.getByTestId('receptionist-intake-branch-note')).toHaveTextContent(
      'No branch is assigned',
    )
    const submitButton = screen.getByTestId('receptionist-intake-submit')
    expect(submitButton).toBeDisabled()
    // No client-side error is rendered up-front; the disabled button is
    // the canonical guard so the receptionist cannot accidentally post
    // a record with no branch.
    expect(screen.queryByTestId('receptionist-intake-error')).not.toBeInTheDocument()
  })
})
