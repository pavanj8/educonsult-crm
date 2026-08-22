import { useEffect, useId, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { isApiError } from '../api/client'
import { requestPasswordReset } from '../api/auth'
import { LOGIN_PATH } from '../routes/ProtectedRoute'
import { useAuth } from '../store/authStore'

export default function ForgotPasswordPage() {
  const navigate = useNavigate()
  const { isAuthenticated, isLoading } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const errorId = useId()

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, isLoading, navigate])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    const formData = new FormData(event.currentTarget)
    const email = formData.get('email')
    const trimmedEmail = typeof email === 'string' ? email.trim() : ''

    try {
      await requestPasswordReset({ email: trimmedEmail })
      setSubmitted(true)
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message)
      } else {
        setError('Unable to send reset email')
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
      <div className="login-page__card">
        <h1>Forgot password</h1>
        {submitted ? (
          <>
            <p className="login-page__subtitle">
              If an account exists for that email, a reset link has been sent. Please check your
              inbox and follow the link to choose a new password.
            </p>
            <p className="login-page__footer">
              <Link to={LOGIN_PATH} className="login-page__link">
                Back to sign in
              </Link>
            </p>
          </>
        ) : (
          <>
            <p className="login-page__subtitle">
              Enter the email associated with your account and we&apos;ll send you a link to reset
              your password.
            </p>
            <form className="login-form" method="post" onSubmit={handleSubmit}>
              <label className="login-form__field">
                Email
                <input
                  data-testid="forgot-email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  required
                  aria-describedby={error ? errorId : undefined}
                />
              </label>
              {error ? (
                <p
                  className="login-form__error"
                  data-testid="forgot-error"
                  id={errorId}
                  role="alert"
                >
                  {error}
                </p>
              ) : null}
              <button
                className="login-form__submit"
                data-testid="forgot-submit"
                type="submit"
                disabled={submitting}
                aria-busy={submitting}
              >
                {submitting ? 'Sending…' : 'Send reset link'}
              </button>
            </form>
            <p className="login-page__footer">
              Remembered your password?{' '}
              <Link to={LOGIN_PATH} className="login-page__link">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </main>
  )
}