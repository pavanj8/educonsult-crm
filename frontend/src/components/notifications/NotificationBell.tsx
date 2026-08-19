import { useEffect, useRef, useState } from 'react'

import { useNotifications } from '../../hooks/useNotifications'
import NotificationCenter from './NotificationCenter'

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const bellButtonRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const {
    notifications,
    unreadCount,
    loading,
    error,
    actionError,
    reload,
    markRead,
    markAllRead,
  } = useNotifications()

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
        bellButtonRef.current?.focus()
      }
    }

    if (open) {
      document.addEventListener('keydown', handleKeyDown)
      return () => document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  useEffect(() => {
    if (open) {
      panelRef.current?.focus()
    }
  }, [open])

  function toggleOpen() {
    const nextOpen = !open
    setOpen(nextOpen)
    if (nextOpen) {
      void reload()
    }
  }

  return (
    <div className="notification-bell" ref={containerRef}>
      <button
        ref={bellButtonRef}
        type="button"
        className="notification-bell__button"
        aria-label="Notifications"
        aria-expanded={open}
        aria-haspopup="true"
        onClick={toggleOpen}
      >
        <svg
          className="notification-bell__icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="notification-bell__badge" aria-label={`${unreadCount} unread notifications`}>
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>
      <div ref={panelRef} tabIndex={-1} className="notification-bell__panel">
        <NotificationCenter
          open={open}
          notifications={notifications}
          loading={loading}
          error={error}
          actionError={actionError}
          unreadCount={unreadCount}
          onMarkRead={markRead}
          onMarkAllRead={markAllRead}
        />
      </div>
    </div>
  )
}
