/**
 * Tests for the development-only demo account picker.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DemoAccountPicker } from './DemoAccountPicker'
import { DEMO_ACCOUNTS, DEMO_PASSWORD, demoLoginsEnabled } from '../../auth/demoAccounts'

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('demoLoginsEnabled', () => {
  it('is on for a dev server', () => {
    vi.stubEnv('DEV', true)
    expect(demoLoginsEnabled()).toBe(true)
  })

  it('is off for a production build unless explicitly opted in', () => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_ENABLE_DEMO_LOGINS', '')
    expect(demoLoginsEnabled()).toBe(false)
  })

  it('can be opted into for a throwaway demo deployment', () => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_ENABLE_DEMO_LOGINS', 'true')
    expect(demoLoginsEnabled()).toBe(true)
  })

  it('treats any value other than the exact string "true" as off', () => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_ENABLE_DEMO_LOGINS', '1')
    expect(demoLoginsEnabled()).toBe(false)
  })
})

describe('DemoAccountPicker', () => {
  it('renders nothing when demo logins are disabled', () => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_ENABLE_DEMO_LOGINS', '')

    const { container } = render(<DemoAccountPicker onSignIn={vi.fn()} />)

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByTestId('demo-accounts')).not.toBeInTheDocument()
  })

  it('lists one button per seeded account, labelled by role', () => {
    render(<DemoAccountPicker onSignIn={vi.fn()} />)

    expect(screen.getByTestId('demo-accounts')).toBeInTheDocument()
    for (const account of DEMO_ACCOUNTS) {
      const button = screen.getByTestId(`demo-account-${account.email}`)
      expect(button).toHaveTextContent(account.role)
      expect(button).toHaveTextContent(account.name)
    }
  })

  it('signs in with the seeded password for the account that was clicked', async () => {
    const onSignIn = vi.fn().mockResolvedValue(undefined)
    render(<DemoAccountPicker onSignIn={onSignIn} />)

    await userEvent.click(screen.getByTestId('demo-account-owner@apex.demo.test'))

    expect(onSignIn).toHaveBeenCalledWith('owner@apex.demo.test', DEMO_PASSWORD)
    expect(onSignIn).toHaveBeenCalledTimes(1)
  })

  it('surfaces a seed-aware error when sign-in fails', async () => {
    const onSignIn = vi.fn().mockRejectedValue(new Error('nope'))
    render(<DemoAccountPicker onSignIn={onSignIn} />)

    await userEvent.click(screen.getByTestId('demo-account-counselor@demo.test'))

    await waitFor(() => {
      expect(screen.getByTestId('demo-accounts-error')).toHaveTextContent(/demo seed/i)
    })
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('re-enables the buttons after a failed attempt so another can be tried', async () => {
    const onSignIn = vi.fn().mockRejectedValue(new Error('nope'))
    render(<DemoAccountPicker onSignIn={onSignIn} />)

    const button = screen.getByTestId('demo-account-student@apex.demo.test')
    await userEvent.click(button)

    await waitFor(() => expect(button).not.toBeDisabled())
  })

  it('disables the buttons while the parent form is submitting', () => {
    render(<DemoAccountPicker onSignIn={vi.fn()} disabled />)

    for (const account of DEMO_ACCOUNTS) {
      expect(screen.getByTestId(`demo-account-${account.email}`)).toBeDisabled()
    }
  })
})
