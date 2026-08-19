import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

type LoginResponse = {
  access_token: string
  refresh_token?: string
}

export default function LoginPage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    const formData = new FormData(event.currentTarget)
    const email = formData.get('email')
    const password = formData.get('password')

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(body.detail ?? 'Invalid email or password')
        return
      }

      const tokens = (await response.json()) as LoginResponse
      localStorage.setItem('access_token', tokens.access_token)
      if (tokens.refresh_token) {
        localStorage.setItem('refresh_token', tokens.refresh_token)
      }
      navigate('/')
    } catch {
      setError('Unable to sign in')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-page__card">
        <h1>Sign in</h1>
        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-form__field">
            Email
            <input
              data-testid="login-email"
              name="email"
              type="email"
              autoComplete="username"
              required
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
            />
          </label>
          {error ? (
            <p className="login-form__error" data-testid="login-error" role="alert">
              {error}
            </p>
          ) : null}
          <button
            className="login-form__submit"
            data-testid="login-submit"
            type="submit"
            disabled={submitting}
          >
            Sign in
          </button>
        </form>
      </div>
    </main>
  )
}
