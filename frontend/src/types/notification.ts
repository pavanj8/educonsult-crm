export interface Notification {
  id: number
  title: string
  message: string
  read_at: string | null
  created_at: string
}

export interface NotificationListResponse {
  items: Notification[]
  unread_count: number
}
