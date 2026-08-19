import { useCallback, useEffect, useState } from 'react'

import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/notifications'
import type { Notification } from '../types/notification'

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadNotifications = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchNotifications()
      setNotifications(data.items ?? [])
      setUnreadCount(data.unread_count ?? 0)
    } catch {
      setError('Failed to load notifications')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadNotifications()
  }, [loadNotifications])

  const markRead = useCallback(async (id: number) => {
    try {
      const wasUnread = notifications.find((item) => item.id === id)?.read_at === null
      const updated = await markNotificationRead(id)
      setNotifications((prev) =>
        prev.map((item) => (item.id === id ? updated : item)),
      )
      if (wasUnread && updated.read_at) {
        setUnreadCount((prev) => Math.max(0, prev - 1))
      }
    } catch {
      setError('Failed to mark notification as read')
    }
  }, [notifications])

  const markAllRead = useCallback(async () => {
    try {
      await markAllNotificationsRead()
      setNotifications((prev) =>
        prev.map((item) => ({
          ...item,
          read_at: item.read_at ?? new Date().toISOString(),
        })),
      )
      setUnreadCount(0)
    } catch {
      setError('Failed to mark all notifications as read')
    }
  }, [])

  return {
    notifications,
    unreadCount,
    loading,
    error,
    reload: loadNotifications,
    markRead,
    markAllRead,
  }
}
