/**
 * One-click sign-in for the seeded demo accounts (development only).
 *
 * Sits below the real login form rather than replacing it, so the normal
 * email/password path stays the thing under test. Copy is deliberately in
 * plain English and not routed through i18n: this is developer tooling, not
 * product surface, and translating it would imply it ships to users.
 */

import { useState } from 'react'

import { isApiError } from '../../api/client'
import { DEMO_ACCOUNTS, DEMO_PASSWORD, demoLoginsEnabled } from '../../auth/demoAccounts'
import type { DemoAccount } from '../../auth/demoAccounts'

interface DemoAccountPickerProps {
  /** Same `login` the form uses, so both paths share one code path. */
  onSignIn: (email: string, password: string) => Promise<void>
  /** Disables the buttons while the parent form is mid-submit. */
  disabled?: boolean
}

export function DemoAccountPicker({ onSignIn, disabled = false }: DemoAccountPickerProps) {
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!demoLoginsEnabled()) {
    return null
  }

  async function handlePick(account: DemoAccount) {
    setError(null)
    setPending(account.email)
    try {
      await onSignIn(account.email, DEMO_PASSWORD)
    } catch (err) {
      // The usual cause is a database without the demo seed applied, which is
      // worth saying out loud rather than showing a bare "invalid credentials".
      setError(
        isApiError(err)
          ? `${err.message} — has the demo seed been applied to this database?`
          : 'Demo sign-in failed. Is the backend running with the demo seed applied?',
      )
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="demo-accounts" data-testid="demo-accounts" aria-labelledby="demo-accounts-heading">
      <h2 className="demo-accounts__heading" id="demo-accounts-heading">
        Demo accounts
        <span className="demo-accounts__badge">dev only</span>
      </h2>
      <p className="demo-accounts__note">
        Seeded sign-ins for local development. Every account uses the password{' '}
        <code>{DEMO_PASSWORD}</code>.
      </p>

      {error ? (
        <p className="demo-accounts__error" role="alert" data-testid="demo-accounts-error">
          {error}
        </p>
      ) : null}

      <ul className="demo-accounts__list">
        {DEMO_ACCOUNTS.map((account) => (
          <li key={account.email}>
            <button
              type="button"
              className="demo-accounts__item"
              data-testid={`demo-account-${account.email}`}
              onClick={() => handlePick(account)}
              disabled={disabled || pending !== null}
              aria-busy={pending === account.email}
            >
              <span className="demo-accounts__role">{account.role}</span>
              <span className="demo-accounts__name">
                {pending === account.email ? 'Signing in…' : account.name}
              </span>
              <span className="demo-accounts__hint">{account.hint}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
