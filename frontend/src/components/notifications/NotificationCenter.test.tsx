import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import NotificationCenter from './NotificationCenter'
import type { Notification } from '../../types/notification'

const notifications: Notification[] = [
  {
    id: 1,
    title: 'Stage updated',
    message: 'Your application moved to Counseling.',
    read_at: null,
    created_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 2,
    title: 'Document rejected',
    message: 'Please re-upload your transcript.',
    read_at: '2026-01-14T09:00:00Z',
    created_at: '2026-01-14T09:00:00Z',
  },
]

describe('NotificationCenter', () => {
  it('does not render when closed', () => {
    render(
      <NotificationCenter
        open={false}
        notifications={notifications}
        loading={false}
        error={null}
        unreadCount={1}
        onMarkRead={vi.fn()}
        onMarkAllRead={vi.fn()}
      />,
    )

    expect(screen.queryByTestId('notification-center')).not.toBeInTheDocument()
  })

  it('renders notifications and mark-read controls when open', () => {
    render(
      <NotificationCenter
        open
        notifications={notifications}
        loading={false}
        error={null}
        unreadCount={1}
        onMarkRead={vi.fn()}
        onMarkAllRead={vi.fn()}
      />,
    )

    expect(screen.getByRole('region', { name: 'Notification center' })).toBeInTheDocument()
    expect(screen.getByText('Stage updated')).toBeInTheDocument()
    expect(screen.getByText('Document rejected')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark all read' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark "Stage updated" as read' })).toBeInTheDocument()
  })

  it('shows empty state when there are no notifications', () => {
    render(
      <NotificationCenter
        open
        notifications={[]}
        loading={false}
        error={null}
        unreadCount={0}
        onMarkRead={vi.fn()}
        onMarkAllRead={vi.fn()}
      />,
    )

    expect(screen.getByText('No notifications yet.')).toBeInTheDocument()
  })

  it('calls mark-read handlers', async () => {
    const user = userEvent.setup()
    const onMarkRead = vi.fn()
    const onMarkAllRead = vi.fn()

    render(
      <NotificationCenter
        open
        notifications={notifications}
        loading={false}
        error={null}
        unreadCount={1}
        onMarkRead={onMarkRead}
        onMarkAllRead={onMarkAllRead}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Mark "Stage updated" as read' }))
    await user.click(screen.getByRole('button', { name: 'Mark all read' }))

    expect(onMarkRead).toHaveBeenCalledWith(1)
    expect(onMarkAllRead).toHaveBeenCalled()
  })
})
