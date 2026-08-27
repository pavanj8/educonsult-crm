/**
 * Signed-in identity and sign-out, in the app header.
 *
 * The shell previously showed no indication of who was signed in and offered
 * no way out: ``logout()`` existed in the auth store and was called on a 401,
 * but nothing in the UI ever invoked it, for any role. Clearing site data was
 * the only way to end a session.
 *
 * Open/close behaviour deliberately mirrors NotificationBell (click outside,
 * Escape returns focus to the trigger) so the two header menus behave the same.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../../store/authStore'
import { USER_ROLE_LABELS } from '../../types/auth'

export default function AccountMenu() {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const { user, logout } = useAuth()
  const { t } = useTranslation()

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    if (open) {
      document.addEventListener('keydown', handleKeyDown)
      return () => document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  if (!user) {
    return null
  }

  const roleLabel = USER_ROLE_LABELS[user.role] ?? user.role

  function handleSignOut() {
    setOpen(false)
    // Clearing the session is the whole job; ProtectedRoute owns where the
    // user lands next. Navigating from here as well does not work and is worth
    // recording, because both orderings look correct:
    //
    //   logout() then navigate() -- clearing auth makes ProtectedRoute redirect
    //     immediately, which unmounts this component, and React Router drops
    //     the queued navigation from an unmounting component.
    //   navigate() then logout() -- arrives at /login still authenticated, and
    //     LoginPage's own "already signed in" effect bounces straight back.
    //
    // So a signed-out user lands wherever ProtectedRoute sends them: the
    // landing page from the app root, the login form from anywhere deeper.
    logout()
  }

  return (
    <div className="account-menu" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        className="account-menu__trigger"
        data-testid="account-menu-trigger"
        aria-label={t('app.account.menu')}
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen((wasOpen) => !wasOpen)}
      >
        <span className="account-menu__avatar" aria-hidden="true">
          {user.email.slice(0, 1).toUpperCase()}
        </span>
        <span className="account-menu__role">{roleLabel}</span>
      </button>

      {open ? (
        <div className="account-menu__panel" data-testid="account-menu-panel" role="menu">
          <div className="account-menu__identity">
            <p className="account-menu__email" data-testid="account-menu-email">
              {user.email}
            </p>
            <p className="account-menu__meta">{roleLabel}</p>
          </div>
          <button
            type="button"
            className="account-menu__signout"
            data-testid="account-menu-signout"
            role="menuitem"
            onClick={handleSignOut}
          >
            {t('app.account.signOut')}
          </button>
        </div>
      ) : null}
    </div>
  )
}
