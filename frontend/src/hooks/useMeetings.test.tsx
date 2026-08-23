import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  useApplicationMeetings,
  useScheduleMeeting,
} from './useMeetings'

const meeting = {
  id: 99,
  tenant_id: 10,
  application_id: 5,
  counselor_id: 7,
  student_id: 42,
  scheduled_at: '2026-05-01T09:30:00Z',
  duration_minutes: 30,
  location: 'Room 2',
  notes: null,
  created_at: '2026-04-01T09:00:00Z',
  updated_at: '2026-04-01T09:00:00Z',
}

function makeFetch(handler: (path: string, init?: RequestInit) => Promise<Response>) {
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = typeof url === 'string' ? url : url.toString()
    return handler(path, init)
  }) as unknown as typeof fetch
}

describe('useApplicationMeetings', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('does not fetch without an access token', async () => {
    const fetchMock = vi.fn() as unknown as typeof fetch
    globalThis.fetch = fetchMock
    const { result } = renderHook(() => useApplicationMeetings(5))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.meetings).toEqual([])
    expect(result.current.error).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads meetings when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/applications/5/meetings')) {
        return { ok: true, status: 200, json: async () => [meeting] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    const { result } = renderHook(() => useApplicationMeetings(5))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.meetings).toEqual([meeting])
    expect(result.current.error).toBeNull()
  })

  it('maps 403 to a permission error', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    } as unknown as Response))

    const { result } = renderHook(() => useApplicationMeetings(5))
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

    const { result } = renderHook(() => useApplicationMeetings(5))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toMatch(/sign in/i)
  })

  it('maps 404 to an application-not-found message', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Application not found' }),
    } as unknown as Response))

    const { result } = renderHook(() => useApplicationMeetings(5))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toMatch(/not found/i)
  })
})

describe('useScheduleMeeting', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('schedules the meeting and fires the success callback', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = makeFetch(async (path, init) => {
      if (path.includes('/applications/5/meetings') && init?.method === 'POST') {
        return { ok: true, status: 201, json: async () => meeting } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    const { result } = renderHook(() => useScheduleMeeting())
    const onScheduled = vi.fn()
    const { meeting: created, errorMessage } = await result.current.schedule(
      5,
      { scheduled_at: '2026-05-01T09:30:00Z', duration_minutes: 30 },
      onScheduled,
    )

    expect(created).toEqual(meeting)
    expect(errorMessage).toBeNull()
    expect(onScheduled).toHaveBeenCalledWith(meeting)
  })

  it('surfaces a 422 backend detail message on failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'duration_minutes must be > 0' }),
    } as unknown as Response))

    const { result } = renderHook(() => useScheduleMeeting())
    const { meeting: created, errorMessage } = await result.current.schedule(5, {
      scheduled_at: '2026-05-01T09:30:00Z',
      duration_minutes: 0,
    })
    expect(created).toBeNull()
    expect(errorMessage).toMatch(/duration/i)
  })

  it('surfaces a 403 backend detail message on permission failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    } as unknown as Response))

    const { result } = renderHook(() => useScheduleMeeting())
    const { meeting: created, errorMessage } = await result.current.schedule(5, {
      scheduled_at: '2026-05-01T09:30:00Z',
      duration_minutes: 30,
    })
    expect(created).toBeNull()
    expect(errorMessage).toMatch(/permission/i)
  })
})
