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
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders the bell button with unread badge', async () => {
    globalThis.fetch = mockFetchResponse(mockNotifications) as typeof fetch

    render(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
    })

    expect(screen.getByLabelText('1 unread notifications')).toHaveTextContent('1')
  })

  it('shows 99+ badge when unread count exceeds 99', async () => {
    globalThis.fetch = mockFetchResponse({
      items: [],
      unread_count: 150,
    }) as typeof fetch

    render(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByLabelText('150 unread notifications')).toHaveTextContent('99+')
    })
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

  it('shows loading state when panel is opened', async () => {
    const user = userEvent.setup()
    let resolveFetch: (value: unknown) => void
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve
    })
    globalThis.fetch = vi.fn().mockReturnValue(fetchPromise) as typeof fetch

    render(<NotificationBell />)

    await waitFor(() => {
      expect(resultOrBellReady()).toBeTruthy()
    })

    await user.click(screen.getByRole('button', { name: 'Notifications' }))

    expect(screen.getByText('Loading notifications…')).toBeInTheDocument()

    resolveFetch!({
      ok: true,
      status: 200,
      json: async () => mockNotifications,
    })

    await waitFor(() => {
      expect(screen.getByText('Document approved')).toBeInTheDocument()
    })
  })

  it('shows load error state in the panel', async () => {
    const user = userEvent.setup()
    globalThis.fetch = mockFetchResponse({}, 500) as typeof fetch

    render(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Notifications' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Failed to load notifications')
    })
  })

  it('closes the panel when clicking outside', async () => {
    const user = userEvent.setup()
    globalThis.fetch = mockFetchResponse(mockNotifications) as typeof fetch

    render(
      <div>
        <NotificationBell />
        <button type="button">Outside</button>
      </div>,
    )

    await waitFor(() => {
      expect(screen.getByLabelText('1 unread notifications')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(screen.getByTestId('notification-center')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Outside' }))
    expect(screen.queryByTestId('notification-center')).not.toBeInTheDocument()
  })

  it('closes the panel and returns focus when Escape is pressed', async () => {
    const user = userEvent.setup()
    globalThis.fetch = mockFetchResponse(mockNotifications) as typeof fetch

    render(<NotificationBell />)

    const bellButton = screen.getByRole('button', { name: 'Notifications' })

    await waitFor(() => {
      expect(screen.getByLabelText('1 unread notifications')).toBeInTheDocument()
    })

    await user.click(bellButton)
    expect(screen.getByTestId('notification-center')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(screen.queryByTestId('notification-center')).not.toBeInTheDocument()
    expect(bellButton).toHaveFocus()
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

  it('shows action error when mark-read fails but keeps list visible', async () => {
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
        ok: false,
        status: 500,
        json: async () => ({}),
      })
    globalThis.fetch = fetchMock as typeof fetch

    render(<NotificationBell />)

    await waitFor(() => {
      expect(screen.getByLabelText('1 unread notifications')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Notifications' }))
    await user.click(screen.getByRole('button', { name: 'Mark "Document approved" as read' }))

    await waitFor(() => {
      expect(screen.getByTestId('notification-action-error')).toHaveTextContent(
        'Failed to mark notification as read',
      )
    })

    expect(screen.getByText('Document approved')).toBeInTheDocument()
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
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          items: mockNotifications.items.map((item) => ({
            ...item,
            read_at: item.read_at ?? '2026-01-15T12:00:00Z',
          })),
          unread_count: 0,
        }),
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

function resultOrBellReady(): boolean {
  return screen.queryByRole('button', { name: 'Notifications' }) !== null
}
