import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/notifications'
import type { Notification } from '../types/notification'

function hasAccessToken(): boolean {
  return localStorage.getItem('access_token') !== null
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const loadNotifications = useCallback(async () => {
    if (!hasAccessToken()) {
      setNotifications([])
      setUnreadCount(0)
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await fetchNotifications()
      setNotifications(data.items ?? [])
      setUnreadCount(data.unread_count ?? 0)
    } catch (err) {
      const message = isApiError(err) ? err.message : 'Failed to load notifications'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadNotifications()
  }, [loadNotifications])

  const markRead = useCallback(async (id: number) => {
    setActionError(null)
    try {
      const updated = await markNotificationRead(id)
      let wasUnread = false
      setNotifications((prev) =>
        prev.map((item) => {
          if (item.id === id) {
            wasUnread = item.read_at === null
            return updated
          }
          return item
        }),
      )
      if (wasUnread && updated.read_at) {
        setUnreadCount((prev) => Math.max(0, prev - 1))
      }
    } catch {
      setActionError('Failed to mark notification as read')
    }
  }, [])

  const markAllRead = useCallback(async () => {
    setActionError(null)
    try {
      await markAllNotificationsRead()
      await loadNotifications()
    } catch {
      setActionError('Failed to mark all notifications as read')
    }
  }, [loadNotifications])

  return {
    notifications,
    unreadCount,
    loading,
    error,
    actionError,
    reload: loadNotifications,
    markRead,
    markAllRead,
  }
}
