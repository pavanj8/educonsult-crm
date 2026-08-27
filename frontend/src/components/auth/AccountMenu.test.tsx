/**
 * Tests for the header account menu (identity + sign out).
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import AccountMenu from './AccountMenu'
import { initI18n } from '../../i18n'
import type { AuthUser } from '../../types/auth'

const mockLogout = vi.fn()
const mockUseAuth = vi.fn()

vi.mock('../../store/authStore', () => ({
  useAuth: () => mockUseAuth(),
}))

beforeAll(() => {
  initI18n('en')
})

function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: 1,
    email: 'super_admin@demo.test',
    role: 'super_admin',
    tenant_id: null,
    branch_id: null,
    ...overrides,
  }
}

function renderMenu(user: AuthUser | null = makeUser()) {
  mockUseAuth.mockReturnValue({ user, logout: mockLogout })
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<AccountMenu />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AccountMenu', () => {
  beforeEach(() => {
    mockLogout.mockReset()
    mockUseAuth.mockReset()
  })

  it('renders nothing when there is no signed-in user', () => {
    const { container } = renderMenu(null)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the signed-in role on the trigger, collapsed by default', () => {
    renderMenu()

    const trigger = screen.getByTestId('account-menu-trigger')
    expect(trigger).toHaveTextContent('Super Admin')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByTestId('account-menu-panel')).not.toBeInTheDocument()
  })

  it('reveals the email and role when opened', async () => {
    renderMenu()

    await userEvent.click(screen.getByTestId('account-menu-trigger'))

    expect(screen.getByTestId('account-menu-panel')).toBeInTheDocument()
    expect(screen.getByTestId('account-menu-email')).toHaveTextContent('super_admin@demo.test')
    expect(screen.getByTestId('account-menu-trigger')).toHaveAttribute('aria-expanded', 'true')
  })

  it('labels every role, including the ones staff cannot create', () => {
    // super_admin / consultancy_owner / student are absent from
    // STAFF_ROLE_LABELS, which is why the menu uses the full map.
    for (const [role, label] of [
      ['super_admin', 'Super Admin'],
      ['consultancy_owner', 'Consultancy Owner'],
      ['student', 'Student'],
      ['counselor', 'Counselor'],
    ] as const) {
      const { unmount } = renderMenu(makeUser({ role }))
      expect(screen.getByTestId('account-menu-trigger')).toHaveTextContent(label)
      unmount()
    }
  })

  it('clears the session and closes when signing out', async () => {
    renderMenu()

    await userEvent.click(screen.getByTestId('account-menu-trigger'))
    await userEvent.click(screen.getByTestId('account-menu-signout'))

    expect(mockLogout).toHaveBeenCalledTimes(1)
    // Where the user lands is ProtectedRoute's call, not this component's --
    // see the sign-out case in routes.test.tsx for that half.
    await waitFor(() => {
      expect(screen.queryByTestId('account-menu-panel')).not.toBeInTheDocument()
    })
  })

  it('closes on Escape and returns focus to the trigger', async () => {
    renderMenu()

    const trigger = screen.getByTestId('account-menu-trigger')
    await userEvent.click(trigger)
    expect(screen.getByTestId('account-menu-panel')).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')

    await waitFor(() => {
      expect(screen.queryByTestId('account-menu-panel')).not.toBeInTheDocument()
    })
    expect(trigger).toHaveFocus()
  })

  it('closes when clicking outside', async () => {
    renderMenu()

    await userEvent.click(screen.getByTestId('account-menu-trigger'))
    expect(screen.getByTestId('account-menu-panel')).toBeInTheDocument()

    await userEvent.click(document.body)

    await waitFor(() => {
      expect(screen.queryByTestId('account-menu-panel')).not.toBeInTheDocument()
    })
  })
})
