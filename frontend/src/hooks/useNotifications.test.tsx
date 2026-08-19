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
  })

  it('loads notifications on mount', async () => {
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

  it('sets error when fetch fails', async () => {
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
})
