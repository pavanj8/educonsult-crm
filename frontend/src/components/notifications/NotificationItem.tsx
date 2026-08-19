import type { Notification } from '../../types/notification'

interface NotificationItemProps {
  notification: Notification
  onMarkRead: (id: number) => void
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString()
}

export default function NotificationItem({ notification, onMarkRead }: NotificationItemProps) {
  const isUnread = notification.read_at === null

  return (
    <li
      className={`notification-item${isUnread ? ' notification-item--unread' : ''}`}
      data-testid={`notification-item-${notification.id}`}
    >
      <div className="notification-item__content">
        <p className="notification-item__title">{notification.title}</p>
        <p className="notification-item__message">{notification.message}</p>
        <time className="notification-item__time" dateTime={notification.created_at}>
          {formatTimestamp(notification.created_at)}
        </time>
      </div>
      {isUnread && (
        <button
          type="button"
          className="notification-item__mark-read"
          aria-label={`Mark "${notification.title}" as read`}
          onClick={() => onMarkRead(notification.id)}
        >
          Mark read
        </button>
      )}
    </li>
  )
}
