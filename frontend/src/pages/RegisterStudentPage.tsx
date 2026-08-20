import { useEffect, useId, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { isApiError } from '../api/client'
import StudyPreferencesFieldset from '../components/master-data/StudyPreferencesFieldset'
import { useDebouncedTenantSlug } from '../hooks/useMasterData'
import { LOGIN_PATH } from '../routes/ProtectedRoute'
import { useAuth } from '../store/authStore'
import { REGISTER_PATH } from '../routes/paths'

function postRegisterPath(location: ReturnType<typeof useLocation>): string {
  const state = location.state
  if (state && typeof state === 'object' && 'from' in state) {
    const from = state.from as { pathname?: string } | undefined
    const pathname = from?.pathname
    if (
      typeof pathname === 'string' &&
      pathname.startsWith('/') &&
      pathname !== LOGIN_PATH &&
      pathname !== REGISTER_PATH
    ) {
      return pathname
    }
  }
  return '/'
}

export default function RegisterStudentPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { registerStudent, clearError, isAuthenticated, isLoading } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [tenantSlugInput, setTenantSlugInput] = useState('')
  const tenantSlug = useDebouncedTenantSlug(tenantSlugInput)
  const [countryId, setCountryId] = useState<number | ''>('')
  const [universityId, setUniversityId] = useState<number | ''>('')
  const [programId, setProgramId] = useState<number | ''>('')
  const errorId = useId()

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate(postRegisterPath(location), { replace: true })
    }
  }, [isAuthenticated, isLoading, location, navigate])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    clearError()
    setSubmitting(true)

    const formData = new FormData(event.currentTarget)
    const tenantSlug = formData.get('tenant_slug')
    const branchId = formData.get('branch_id')
    const name = formData.get('name')
    const email = formData.get('email')
    const password = formData.get('password')
    const phone = formData.get('phone')
    const dateOfBirth = formData.get('date_of_birth')

    const trimmedTenantSlug = typeof tenantSlug === 'string' ? tenantSlug.trim() : ''
    const branchIdValue = typeof branchId === 'string' ? Number.parseInt(branchId, 10) : Number.NaN
    const trimmedName = typeof name === 'string' ? name.trim() : ''
    const trimmedEmail = typeof email === 'string' ? email.trim() : ''
    const passwordValue = typeof password === 'string' ? password : ''
    const trimmedPhone = typeof phone === 'string' ? phone.trim() : ''
    const dateOfBirthValue = typeof dateOfBirth === 'string' ? dateOfBirth : ''

    if (!Number.isFinite(branchIdValue) || branchIdValue < 1) {
      setError('Branch ID must be a positive number')
      setSubmitting(false)
      return
    }

    try {
      await registerStudent({
        tenant_slug: trimmedTenantSlug,
        branch_id: branchIdValue,
        name: trimmedName,
        email: trimmedEmail,
        password: passwordValue,
        phone: trimmedPhone,
        date_of_birth: dateOfBirthValue,
        ...(typeof countryId === 'number' ? { target_country_id: countryId } : {}),
        ...(typeof universityId === 'number' ? { target_university_id: universityId } : {}),
        ...(typeof programId === 'number' ? { target_program_id: programId } : {}),
      })
      navigate(postRegisterPath(location), { replace: true })
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message)
      } else {
        setError('Unable to create account')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if ((isLoading && !submitting) || isAuthenticated) {
    return (
      <main className="login-page">
        <div className="auth-loading" role="status" aria-live="polite" aria-label="Loading">
          Loading…
        </div>
      </main>
    )
  }

  return (
    <main className="login-page">
      <div className="login-page__card login-page__card--wide">
        <h1>Create student account</h1>
        <p className="login-page__subtitle">Register to start your study abroad journey.</p>
        <form className="login-form" method="post" onSubmit={handleSubmit}>
          <fieldset className="login-form__section">
            <legend>Consultancy</legend>
            <label className="login-form__field">
              Consultancy code
              <input
                data-testid="register-tenant-slug"
                name="tenant_slug"
                type="text"
                autoComplete="organization"
                required
                placeholder="e.g. apex"
                aria-describedby={error ? errorId : undefined}
                onChange={(event) => {
                  setTenantSlugInput(event.target.value)
                  setCountryId('')
                  setUniversityId('')
                  setProgramId('')
                }}
              />
            </label>
            <label className="login-form__field">
              Branch ID
              <input
                data-testid="register-branch-id"
                name="branch_id"
                type="number"
                min={1}
                step={1}
                required
                aria-describedby={error ? errorId : undefined}
              />
            </label>
          </fieldset>
          <StudyPreferencesFieldset
            tenantSlug={tenantSlug}
            countryId={countryId}
            universityId={universityId}
            programId={programId}
            onCountryChange={(value) => {
              setCountryId(value)
              setUniversityId('')
              setProgramId('')
            }}
            onUniversityChange={(value) => {
              setUniversityId(value)
              setProgramId('')
            }}
            onProgramChange={setProgramId}
            describedBy={error ? errorId : undefined}
          />
          <fieldset className="login-form__section">
            <legend>Profile</legend>
            <label className="login-form__field">
              Full name
              <input
                data-testid="register-name"
                name="name"
                type="text"
                autoComplete="name"
                required
                aria-describedby={error ? errorId : undefined}
              />
            </label>
            <label className="login-form__field">
              Email
              <input
                data-testid="register-email"
                name="email"
                type="email"
                autoComplete="email"
                required
                aria-describedby={error ? errorId : undefined}
              />
            </label>
            <label className="login-form__field">
              Password
              <input
                data-testid="register-password"
                name="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                aria-describedby={error ? errorId : undefined}
              />
            </label>
            <label className="login-form__field">
              Phone
              <input
                data-testid="register-phone"
                name="phone"
                type="tel"
                autoComplete="tel"
                required
                aria-describedby={error ? errorId : undefined}
              />
            </label>
            <label className="login-form__field">
              Date of birth
              <input
                data-testid="register-date-of-birth"
                name="date_of_birth"
                type="date"
                required
                aria-describedby={error ? errorId : undefined}
              />
            </label>
          </fieldset>
          {error ? (
            <p
              className="login-form__error"
              data-testid="register-error"
              id={errorId}
              role="alert"
            >
              {error}
            </p>
          ) : null}
          <button
            className="login-form__submit"
            data-testid="register-submit"
            type="submit"
            disabled={submitting}
            aria-busy={submitting}
          >
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="login-page__footer">
          Already have an account?{' '}
          <Link to={LOGIN_PATH} className="login-page__link">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  )
}
