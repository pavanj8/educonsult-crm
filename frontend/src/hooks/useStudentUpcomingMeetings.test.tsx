import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useStudentUpcomingMeetings } from './useStudentUpcomingMeetings'

const futureIso = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
const pastIso = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()

const futureMeeting = {
  id: 99,
  tenant_id: 10,
  application_id: 5,
  counselor_id: 7,
  student_id: 42,
  scheduled_at: futureIso,
  duration_minutes: 30,
  location: 'Room 2',
  notes: null,
  created_at: '2026-04-01T09:00:00Z',
  updated_at: '2026-04-01T09:00:00Z',
}

const pastMeeting = {
  ...futureMeeting,
  id: 100,
  scheduled_at: pastIso,
}

function makeFetch(handler: (path: string) => Promise<Response>) {
  return vi.fn(async (url: RequestInfo | URL) => {
    const path = typeof url === 'string' ? url : url.toString()
    return handler(path)
  }) as unknown as typeof fetch
}

describe('useStudentUpcomingMeetings', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('does not fetch without an access token', async () => {
    const fetchMock = vi.fn() as unknown as typeof fetch
    globalThis.fetch = fetchMock
    const { result } = renderHook(() => useStudentUpcomingMeetings())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.upcoming).toEqual([])
    expect(result.current.error).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('returns only future meetings, sorted soonest first', async () => {
    localStorage.setItem('access_token', 'test-token')
    const sooner = {
      ...futureMeeting,
      id: 101,
      scheduled_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    }
    const later = {
      ...futureMeeting,
      id: 102,
      scheduled_at: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(),
    }
    globalThis.fetch = makeFetch(async (path) => {
      if (path.endsWith('/me/meetings')) {
        // Backend returns everything (past + future); the hook filters.
        return { ok: true, status: 200, json: async () => [later, pastMeeting, sooner] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    const { result } = renderHook(() => useStudentUpcomingMeetings())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.upcoming.map((m) => m.id)).toEqual([101, 102])
    expect(result.current.error).toBeNull()
  })

  it('maps 403 to a permission error', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    } as unknown as Response))

    const { result } = renderHook(() => useStudentUpcomingMeetings())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toMatch(/permission/i)
  })

  it('maps 401 to a sign-in message', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Not authenticated' }),
    } as unknown as Response))

    const { result } = renderHook(() => useStudentUpcomingMeetings())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toMatch(/sign in/i)
  })

  it('returns empty upcoming list when all meetings are in the past', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = makeFetch(async (path) => {
      if (path.endsWith('/me/meetings')) {
        return { ok: true, status: 200, json: async () => [pastMeeting] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    const { result } = renderHook(() => useStudentUpcomingMeetings())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.upcoming).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('reload triggers a fresh fetch', async () => {
    localStorage.setItem('access_token', 'test-token')
    let calls = 0
    globalThis.fetch = makeFetch(async (path) => {
      if (path.endsWith('/me/meetings')) {
        calls += 1
        return { ok: true, status: 200, json: async () => [futureMeeting] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    const { result } = renderHook(() => useStudentUpcomingMeetings())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(calls).toBe(1)
    await result.current.reload()
    expect(calls).toBeGreaterThanOrEqual(2)
  })
})