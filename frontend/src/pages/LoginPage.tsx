import { useEffect, useId, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { isApiError } from '../api/client'
import { REGISTER_PATH, FORGOT_PASSWORD_PATH } from '../routes/paths'
import { useAuth } from '../store/authStore'

function postLoginPath(location: ReturnType<typeof useLocation>): string {
  const state = location.state
  if (state && typeof state === 'object' && 'from' in state) {
    const from = state.from as { pathname?: string } | undefined
    const pathname = from?.pathname
    if (typeof pathname === 'string' && pathname.startsWith('/') && pathname !== '/login') {
      return pathname
    }
  }
  return '/'
}

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, clearError, isAuthenticated, isLoading } = useAuth()
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const errorId = useId()

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate(postLoginPath(location), { replace: true })
    }
  }, [isAuthenticated, isLoading, location, navigate])

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
      navigate(postLoginPath(location), { replace: true })
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message)
      } else {
        setError(t('login.errors.fallback'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  if ((isLoading && !submitting) || isAuthenticated) {
    return (
      <main className="login-page">
        <div className="auth-loading" role="status" aria-live="polite" aria-label={t('common.loading')}>
          {t('common.loadingEllipsis')}
        </div>
      </main>
    )
  }

  return (
    <main className="login-page">
      <div className="login-page__card">
        <h1>{t('login.title')}</h1>
        <form className="login-form" method="post" onSubmit={handleSubmit}>
          <label className="login-form__field">
            {t('login.fields.email')}
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
            {t('login.fields.password')}
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
            {submitting ? t('login.submit.submitting') : t('login.submit.idle')}
          </button>
        </form>
        <p className="login-page__footer">
          <Link to={FORGOT_PASSWORD_PATH} className="login-page__link">
            {t('login.links.forgotPassword')}
          </Link>
        </p>
        <p className="login-page__footer">
          {t('login.links.newStudentPrompt')}{' '}
          <Link to={REGISTER_PATH} className="login-page__link">
            {t('login.links.createAccount')}
          </Link>
        </p>
      </div>
    </main>
  )
}
