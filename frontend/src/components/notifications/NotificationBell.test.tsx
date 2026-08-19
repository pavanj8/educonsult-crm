import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import NotificationBell from './NotificationBell'

const mockNotifications = {
  items: [
    {
      id: 1,
      title: 'Document approved',
      message: 'Your passport was approved.',
      read_at: null,
      created_at: '2026-01-15T10:00:00Z',
    },
    {
      id: 2,
      title: 'Meeting scheduled',
      message: 'Counseling session on Friday.',
      read_at: '2026-01-14T09:00:00Z',
      created_at: '2026-01-14T09:00:00Z',
    },
  ],
  unread_count: 1,
}

function mockFetchResponse(data: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  })
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the bell button with unread badge', async () => {
    globalThis.fetch = mockFetchResponse(mockNotifications) as typeof fetch

    render(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
    })

    expect(screen.getByLabelText('1 unread notifications')).toHaveTextContent('1')
  })

  it('opens the notification center when the bell is clicked', async () => {
    const user = userEvent.setup()
    globalThis.fetch = mockFetchResponse(mockNotifications) as typeof fetch

    render(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByLabelText('1 unread notifications')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Notifications' }))

    expect(screen.getByTestId('notification-center')).toBeInTheDocument()
    expect(screen.getByText('Document approved')).toBeInTheDocument()
    expect(screen.getByText('Meeting scheduled')).toBeInTheDocument()
  })

  it('marks a notification as read', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockNotifications,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockNotifications,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          ...mockNotifications.items[0],
          read_at: '2026-01-15T11:00:00Z',
        }),
      })
    globalThis.fetch = fetchMock as typeof fetch

    render(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByLabelText('1 unread notifications')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Notifications' }))
    await user.click(screen.getByRole('button', { name: 'Mark "Document approved" as read' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/notifications/1/read',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })

    expect(screen.queryByRole('button', { name: 'Mark "Document approved" as read' })).not.toBeInTheDocument()
  })

  it('marks all notifications as read', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockNotifications,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockNotifications,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 204,
        json: async () => undefined,
      })
    globalThis.fetch = fetchMock as typeof fetch

    render(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByLabelText('1 unread notifications')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Notifications' }))
    await user.click(screen.getByRole('button', { name: 'Mark all read' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/notifications/read-all',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })

    expect(screen.queryByLabelText(/unread notifications/)).not.toBeInTheDocument()
  })
})
