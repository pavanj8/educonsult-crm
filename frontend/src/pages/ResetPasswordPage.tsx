import { useEffect, useId, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { isApiError } from '../api/client'
import { submitPasswordReset } from '../api/auth'
import { LOGIN_PATH } from '../routes/ProtectedRoute'
import { useAuth } from '../store/authStore'

const MIN_PASSWORD_LENGTH = 8

function readToken(searchParams: URLSearchParams): string {
  const raw = searchParams.get('token')
  return typeof raw === 'string' ? raw.trim() : ''
}

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = useMemo(() => readToken(searchParams), [searchParams])
  const { isAuthenticated, isLoading } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [succeeded, setSucceeded] = useState(false)
  const [missingToken] = useState<boolean>(() => token.length === 0)
  const errorId = useId()

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, isLoading, navigate])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    if (token.length === 0) {
      setError('Reset link is missing or invalid. Please request a new password reset email.')
      return
    }

    const formData = new FormData(event.currentTarget)
    const password = formData.get('new_password')
    const confirmPassword = formData.get('confirm_password')
    const passwordValue = typeof password === 'string' ? password : ''
    const confirmValue = typeof confirmPassword === 'string' ? confirmPassword : ''

    if (passwordValue.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters long`)
      return
    }

    if (passwordValue !== confirmValue) {
      setError('Passwords do not match')
      return
    }

    setSubmitting(true)
    try {
      await submitPasswordReset({ token, new_password: passwordValue })
      setSucceeded(true)
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message)
      } else {
        setError('Unable to reset password')
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

  if (succeeded) {
    return (
      <main className="login-page">
        <div className="login-page__card">
          <h1>Password reset</h1>
          <p className="login-page__subtitle">Your password has been reset successfully.</p>
          <p className="login-page__footer">
            <Link to={LOGIN_PATH} className="login-page__link">
              Sign in with your new password
            </Link>
          </p>
        </div>
      </main>
    )
  }

  const displayedError = missingToken
    ? 'Reset link is missing or invalid. Please request a new password reset email.'
    : error

  return (
    <main className="login-page">
      <div className="login-page__card">
        <h1>Choose a new password</h1>
        <p className="login-page__subtitle">
          Enter a new password for your account. The reset link expires in 1 hour and can only be
          used once.
        </p>
        <form className="login-form" method="post" onSubmit={handleSubmit}>
          <label className="login-form__field">
            New password
            <input
              data-testid="reset-password"
              name="new_password"
              type="password"
              autoComplete="new-password"
              required
              minLength={MIN_PASSWORD_LENGTH}
              aria-describedby={displayedError ? errorId : undefined}
              disabled={missingToken}
            />
          </label>
          <label className="login-form__field">
            Confirm new password
            <input
              data-testid="reset-password-confirm"
              name="confirm_password"
              type="password"
              autoComplete="new-password"
              required
              minLength={MIN_PASSWORD_LENGTH}
              aria-describedby={displayedError ? errorId : undefined}
              disabled={missingToken}
            />
          </label>
          {displayedError ? (
            <p
              className="login-form__error"
              data-testid="reset-error"
              id={errorId}
              role="alert"
            >
              {displayedError}
            </p>
          ) : null}
          <button
            className="login-form__submit"
            data-testid="reset-submit"
            type="submit"
            disabled={submitting || missingToken}
            aria-busy={submitting}
          >
            {submitting ? 'Resetting…' : 'Reset password'}
          </button>
        </form>
        <p className="login-page__footer">
          <Link to={LOGIN_PATH} className="login-page__link">
            Back to sign in
          </Link>
        </p>
      </div>
    </main>
  )
}