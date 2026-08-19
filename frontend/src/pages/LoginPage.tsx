import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { isApiError } from '../api/client'
import { useAuth } from '../store/authStore'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login, clearError } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const errorId = useId()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    clearError()
    setSubmitting(true)

    const formData = new FormData(event.currentTarget)
    const email = formData.get('email')
    const password = formData.get('password')
    const trimmedEmail = typeof email === 'string' ? email.trim() : ''
    const passwordValue = typeof password === 'string' ? password : ''

    try {
      await login(trimmedEmail, passwordValue)
      navigate('/', { replace: true })
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message)
      } else {
        setError('Unable to sign in')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-page__card">
        <h1>Sign in</h1>
        <form className="login-form" method="post" onSubmit={handleSubmit}>
          <label className="login-form__field">
            Email
            <input
              data-testid="login-email"
              name="email"
              type="email"
              autoComplete="username"
              required
              aria-describedby={error ? errorId : undefined}
            />
          </label>
          <label className="login-form__field">
            Password
            <input
              data-testid="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              aria-describedby={error ? errorId : undefined}
            />
          </label>
          {error ? (
            <p
              className="login-form__error"
              data-testid="login-error"
              id={errorId}
              role="alert"
            >
              {error}
            </p>
          ) : null}
          <button
            className="login-form__submit"
            data-testid="login-submit"
            type="submit"
            disabled={submitting}
            aria-busy={submitting}
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </main>
  )
}
