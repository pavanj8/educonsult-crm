import { useEffect, useId, useState } from 'react'
import type { FormEvent } from 'react'

import { createStudentByReceptionist } from '../api/receptionistIntake'
import { isApiError } from '../api/client'
import StudyPreferencesFieldset from '../components/master-data/StudyPreferencesFieldset'
import { useDebouncedTenantSlug } from '../hooks/useMasterData'
import { useBranding } from '../store/brandingStore'
import { useAuth } from '../store/authStore'

/**
 * Receptionist walk-in student intake form (E17; Journey J10).
 *
 * Renders a structured form that lets an authenticated receptionist
 * (already bound to a single branch by the backend) capture the
 * walk-in student's basic profile and submit it to ``POST /students``.
 *
 * Differences from :mod:`RegisterStudentPage` (public E16 flow):
 *
 * * No ``tenant_slug`` field — the tenant is taken from the
 *   receptionist's auth session on the backend.
 * * ``branch_id`` is locked to the receptionist's own branch (read
 *   from the auth store) and shown as read-only context so the
 *   receptionist cannot accidentally cross-branch a record.
 * * The ``password`` field is a temporary one the receptionist hands
 *   to the walk-in; the student can later self-register via E16 to
 *   set their own password. This is what the backend's
 *   ``StaffCreateStudentRequest`` schema requires for every new
 *   student account (see backend/app/schemas/student.py).
 */
export default function ReceptionistIntakePage() {
  const { user } = useAuth()
  const { tenantSlug: brandingSlug } = useBranding()
  const receptionistBranchId = user?.branch_id ?? null

  const [tenantSlugInput, setTenantSlugInput] = useState('')
  const tenantSlug = useDebouncedTenantSlug(tenantSlugInput)
  // When the branding store resolves the receptionist's tenant slug
  // we mirror it into the input so the public master-data endpoints
  // can be queried without the receptionist having to type the code.
  useEffect(() => {
    if (brandingSlug && brandingSlug !== tenantSlugInput) {
      setTenantSlugInput(brandingSlug)
    }
  }, [brandingSlug, tenantSlugInput])

  const [countryId, setCountryId] = useState<number | ''>('')
  const [universityId, setUniversityId] = useState<number | ''>('')
  const [programId, setProgramId] = useState<number | ''>('')

  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [lastIssuedPassword, setLastIssuedPassword] = useState<string | null>(null)
  const errorId = useId()
  const successId = useId()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSuccessMessage(null)
    setLastIssuedPassword(null)

    if (receptionistBranchId == null) {
      setError('Your account is not assigned to a branch. Contact your consultancy owner.')
      return
    }

    const form = event.currentTarget
    const formData = new FormData(form)
    const name = formData.get('name')
    const email = formData.get('email')
    const password = formData.get('password')
    const phone = formData.get('phone')
    const dateOfBirth = formData.get('date_of_birth')

    const trimmedName = typeof name === 'string' ? name.trim() : ''
    const trimmedEmail = typeof email === 'string' ? email.trim() : ''
    const passwordValue = typeof password === 'string' ? password : ''
    const trimmedPhone = typeof phone === 'string' ? phone.trim() : ''
    const dateOfBirthValue = typeof dateOfBirth === 'string' ? dateOfBirth : ''

    if (
      !trimmedName ||
      !trimmedEmail ||
      !passwordValue ||
      !trimmedPhone ||
      !dateOfBirthValue
    ) {
      setError('Name, email, password, phone, and date of birth are required.')
      return
    }

    setSubmitting(true)
    try {
      const created = await createStudentByReceptionist({
        branch_id: receptionistBranchId,
        name: trimmedName,
        email: trimmedEmail,
        password: passwordValue,
        phone: trimmedPhone,
        date_of_birth: dateOfBirthValue,
        ...(typeof countryId === 'number' ? { target_country_id: countryId } : {}),
        ...(typeof universityId === 'number' ? { target_university_id: universityId } : {}),
        ...(typeof programId === 'number' ? { target_program_id: programId } : {}),
      })
      // Keep the temporary password around on the success screen so the
      // receptionist can hand it to the walk-in. The page never persists
      // or transmits it elsewhere — it is shown once on the success
      // banner and cleared the next time the receptionist begins a new
      // intake.
      setLastIssuedPassword(passwordValue)
      setSuccessMessage(`Student ${created.email} has been registered.`)
      // ``event.currentTarget`` is recycled after the async boundary, so
      // reset via the captured form reference and clear the controlled
      // study-preferences state in lockstep with the DOM reset.
      form.reset()
      setCountryId('')
      setUniversityId('')
      setProgramId('')
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message)
      } else {
        setError('Unable to register student')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const branchContextMessage =
    receptionistBranchId == null
      ? 'No branch is assigned to your account.'
      : `New student will be registered to your branch (branch ${receptionistBranchId}).`

  return (
    <div className="receptionist-intake-page" data-testid="receptionist-intake-page">
      <header className="receptionist-intake-page__header">
        <h2>New student intake</h2>
        <p className="receptionist-intake-page__subtitle">
          Register a walk-in student. The student record is created in your tenant and
          branch; they can later self-register to claim their account.
        </p>
      </header>
      <form
        className="receptionist-intake-form"
        method="post"
        onSubmit={handleSubmit}
        aria-describedby={error ? errorId : successMessage ? successId : undefined}
      >
        <p
          className="receptionist-intake-form__branch-note"
          data-testid="receptionist-intake-branch-note"
        >
          {branchContextMessage}
        </p>

        {/* Hidden slug field — kept in sync with the branding store so the
            public master-data endpoints used by the study-preferences
            fieldset resolve the receptionist's tenant automatically. */}
        <input
          data-testid="receptionist-intake-tenant-slug"
          name="tenant_slug"
          type="hidden"
          value={tenantSlugInput}
          onChange={(event) => {
            setTenantSlugInput(event.target.value)
            setCountryId('')
            setUniversityId('')
            setProgramId('')
          }}
        />

        <fieldset className="login-form__section">
          <legend>Study preferences</legend>
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
            describedBy={error ? errorId : successMessage ? successId : undefined}
            idPrefix="intake-"
          />
        </fieldset>

        <fieldset className="login-form__section">
          <legend>Profile</legend>
          <label className="login-form__field">
            Full name
            <input
              data-testid="receptionist-intake-name"
              name="name"
              type="text"
              autoComplete="off"
              required
              maxLength={255}
              aria-describedby={error ? errorId : successMessage ? successId : undefined}
            />
          </label>
          <label className="login-form__field">
            Email
            <input
              data-testid="receptionist-intake-email"
              name="email"
              type="email"
              autoComplete="off"
              required
              maxLength={255}
              aria-describedby={error ? errorId : successMessage ? successId : undefined}
            />
          </label>
          <label className="login-form__field">
            Temporary password
            <input
              data-testid="receptionist-intake-password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={128}
              aria-describedby={error ? errorId : successMessage ? successId : undefined}
            />
          </label>
          <label className="login-form__field">
            Phone
            <input
              data-testid="receptionist-intake-phone"
              name="phone"
              type="tel"
              autoComplete="off"
              required
              maxLength={50}
              aria-describedby={error ? errorId : successMessage ? successId : undefined}
            />
          </label>
          <label className="login-form__field">
            Date of birth
            <input
              data-testid="receptionist-intake-date-of-birth"
              name="date_of_birth"
              type="date"
              required
              aria-describedby={error ? errorId : successMessage ? successId : undefined}
            />
          </label>
        </fieldset>

        {error ? (
          <p
            className="login-form__error"
            data-testid="receptionist-intake-error"
            id={errorId}
            role="alert"
          >
            {error}
          </p>
        ) : null}
        {successMessage ? (
          <div
            className="receptionist-intake-form__success"
            data-testid="receptionist-intake-success"
            id={successId}
            role="status"
          >
            <p>{successMessage}</p>
            {lastIssuedPassword ? (
              <p
                className="receptionist-intake-form__issued-password"
                data-testid="receptionist-intake-issued-password"
              >
                Temporary password: <strong>{lastIssuedPassword}</strong> — hand it to the
                walk-in so they can log in, then keep it private.
              </p>
            ) : null}
          </div>
        ) : null}

        <button
          className="login-form__submit"
          data-testid="receptionist-intake-submit"
          type="submit"
          disabled={submitting || receptionistBranchId == null}
          aria-busy={submitting}
        >
          {submitting ? 'Registering…' : 'Register student'}
        </button>
      </form>
    </div>
  )
}