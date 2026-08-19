import NotificationItem from './NotificationItem'
import type { Notification } from '../../types/notification'

interface NotificationCenterProps {
  open: boolean
  notifications: Notification[]
  loading: boolean
  error: string | null
  unreadCount: number
  onMarkRead: (id: number) => void
  onMarkAllRead: () => void
}

export default function NotificationCenter({
  open,
  notifications,
  loading,
  error,
  unreadCount,
  onMarkRead,
  onMarkAllRead,
}: NotificationCenterProps) {
  if (!open) {
    return null
  }

  return (
    <div
      className="notification-center"
      role="region"
      aria-label="Notification center"
      data-testid="notification-center"
    >
      <div className="notification-center__header">
        <h2 className="notification-center__title">Notifications</h2>
        {unreadCount > 0 && (
          <button
            type="button"
            className="notification-center__mark-all"
            onClick={onMarkAllRead}
          >
            Mark all read
          </button>
        )}
      </div>

      {loading && <p className="notification-center__status">Loading notifications…</p>}
      {error && (
        <p className="notification-center__status notification-center__status--error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && notifications.length === 0 && (
        <p className="notification-center__status">No notifications yet.</p>
      )}
      {!loading && !error && notifications.length > 0 && (
        <ul className="notification-center__list">
          {notifications.map((notification) => (
            <NotificationItem
              key={notification.id}
              notification={notification}
              onMarkRead={onMarkRead}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
