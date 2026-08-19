import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useNotifications } from './useNotifications'

const mockListResponse = {
  items: [
    {
      id: 1,
      title: 'New notification',
      message: 'Something happened.',
      read_at: null,
      created_at: '2026-01-15T10:00:00Z',
    },
  ],
  unread_count: 1,
}

describe('useNotifications', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('loads notifications on mount when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockListResponse,
    }) as typeof fetch

    const { result } = renderHook(() => useNotifications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.notifications).toHaveLength(1)
    expect(result.current.unreadCount).toBe(1)
  })

  it('skips fetch when no access token is present', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useNotifications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.notifications).toHaveLength(0)
    expect(result.current.error).toBeNull()
  })

  it('sets error when fetch fails', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    }) as typeof fetch

    const { result } = renderHook(() => useNotifications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Failed to load notifications')
  })

  it('shows auth-specific error message on 401', async () => {
    localStorage.setItem('access_token', 'expired-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({}),
    }) as typeof fetch

    const { result } = renderHook(() => useNotifications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Sign in to view notifications')
  })

  it('sets actionError without clearing notifications on mark-read failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockListResponse,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({}),
      }) as typeof fetch

    const { result } = renderHook(() => useNotifications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await result.current.markRead(1)

    await waitFor(() => {
      expect(result.current.actionError).toBe('Failed to mark notification as read')
    })

    expect(result.current.notifications).toHaveLength(1)
    expect(result.current.error).toBeNull()
  })

  it('re-fetches notifications after mark-all-read succeeds', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockListResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 204,
        json: async () => undefined,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [], unread_count: 0 }),
      })
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useNotifications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await result.current.markAllRead()

    await waitFor(() => {
      expect(result.current.notifications).toHaveLength(0)
      expect(result.current.unreadCount).toBe(0)
    })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/notifications/read-all', expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/notifications', expect.any(Object))
  })
})
