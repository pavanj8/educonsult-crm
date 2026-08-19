import { apiFetch } from './client'
import type { Notification, NotificationListResponse } from '../types/notification'

export async function fetchNotifications(): Promise<NotificationListResponse> {
  return apiFetch<NotificationListResponse>('/notifications')
}

export async function markNotificationRead(id: number): Promise<Notification> {
  return apiFetch<Notification>(`/notifications/${id}/read`, { method: 'PATCH' })
}

export async function markAllNotificationsRead(): Promise<void> {
  return apiFetch<void>('/notifications/read-all', { method: 'PATCH' })
}
