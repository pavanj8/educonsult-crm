import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  useApplicationNotes,
  useCreateNote,
  useDeleteNote,
  useUpdateNote,
} from './useNotes'
import type { Note } from '../types/note'

const baseNote: Note = {
  id: 1,
  tenant_id: 10,
  student_id: 42,
  application_id: 5,
  author_user_id: 7,
  body: 'Hello, world.',
  created_at: '2026-04-01T09:00:00Z',
  updated_at: '2026-04-01T09:00:00Z',
}

function makeFetch(handler: (path: string, init?: RequestInit) => Promise<Response>) {
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = typeof url === 'string' ? url : url.toString()
    return handler(path, init)
  }) as unknown as typeof fetch
}

describe('useApplicationNotes', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads notes anchored to the application', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/notes') && path.includes('application_id=5')) {
        return { ok: true, status: 200, json: async () => [baseNote] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    const { result } = renderHook(() =>
      useApplicationNotes(5, 42),
    )

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.notes).toEqual([baseNote])
    expect(result.current.error).toBeNull()
  })

  it('returns an empty list without an access token', async () => {
    localStorage.removeItem('access_token')
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() =>
      useApplicationNotes(5, 42),
    )

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.notes).toEqual([])
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('returns an empty list when studentId is null', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() =>
      useApplicationNotes(5, null),
    )

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.notes).toEqual([])
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('maps a 403 to a permission error', async () => {
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    } as unknown as Response))

    const { result } = renderHook(() =>
      useApplicationNotes(5, 42),
    )

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toMatch(/permission/i)
  })
})

describe('useCreateNote', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('posts the note and returns the created object', async () => {
    let capturedInit: RequestInit | undefined
    globalThis.fetch = makeFetch(async (_path, init) => {
      capturedInit = init
      return { ok: true, status: 201, json: async () => baseNote } as Response
    })

    const { result } = renderHook(() => useCreateNote())

    let outcome: { note: Note | null; errorMessage: string | null } = {
      note: null,
      errorMessage: null,
    }
    await act(async () => {
      outcome = await result.current.create(5, 42, { body: 'Hello, world.' })
    })

    expect(outcome.errorMessage).toBeNull()
    expect(outcome.note).toEqual(baseNote)
    expect(capturedInit?.method).toBe('POST')
    expect(JSON.parse((capturedInit?.body ?? '{}') as string)).toEqual({
      student_id: 42,
      application_id: 5,
      body: 'Hello, world.',
    })
  })

  it('returns an error message on 422', async () => {
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'body must not be blank' }),
    } as unknown as Response))

    const { result } = renderHook(() => useCreateNote())

    let outcome: { note: Note | null; errorMessage: string | null } = {
      note: null,
      errorMessage: null,
    }
    await act(async () => {
      outcome = await result.current.create(5, 42, { body: 'Hello, world.' })
    })

    expect(outcome.note).toBeNull()
    expect(outcome.errorMessage).toMatch(/body must not be blank/i)
  })
})

describe('useUpdateNote', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('patches the note body', async () => {
    let capturedInit: RequestInit | undefined
    globalThis.fetch = makeFetch(async (_path, init) => {
      capturedInit = init
      return { ok: true, status: 200, json: async () => baseNote } as Response
    })

    const { result } = renderHook(() => useUpdateNote())

    let outcome: { note: Note | null; errorMessage: string | null } = {
      note: null,
      errorMessage: null,
    }
    await act(async () => {
      outcome = await result.current.update(1, { body: 'Edited.' })
    })

    expect(outcome.errorMessage).toBeNull()
    expect(capturedInit?.method).toBe('PATCH')
    expect(JSON.parse((capturedInit?.body ?? '{}') as string)).toEqual({
      body: 'Edited.',
    })
  })

  it('maps a 403 to a permission error', async () => {
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Only the author may edit it' }),
    } as unknown as Response))

    const { result } = renderHook(() => useUpdateNote())

    let outcome: { note: Note | null; errorMessage: string | null } = {
      note: null,
      errorMessage: null,
    }
    await act(async () => {
      outcome = await result.current.update(1, { body: 'Edited.' })
    })

    expect(outcome.note).toBeNull()
    expect(outcome.errorMessage).toMatch(/permission/i)
  })
})

describe('useDeleteNote', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('deletes the note and reports success', async () => {
    let capturedInit: RequestInit | undefined
    globalThis.fetch = makeFetch(async (_path, init) => {
      capturedInit = init
      return { ok: true, status: 204, json: async () => undefined } as Response
    })

    const { result } = renderHook(() => useDeleteNote())

    let outcome: { ok: boolean; errorMessage: string | null } = {
      ok: false,
      errorMessage: null,
    }
    await act(async () => {
      outcome = await result.current.remove(1)
    })

    expect(outcome.ok).toBe(true)
    expect(outcome.errorMessage).toBeNull()
    expect(capturedInit?.method).toBe('DELETE')
  })

  it('maps a 404 to a not-available error', async () => {
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Note not found' }),
    } as unknown as Response))

    const { result } = renderHook(() => useDeleteNote())

    let outcome: { ok: boolean; errorMessage: string | null } = {
      ok: false,
      errorMessage: null,
    }
    await act(async () => {
      outcome = await result.current.remove(1)
    })

    expect(outcome.ok).toBe(false)
    expect(outcome.errorMessage).toMatch(/no longer available/i)
  })
})
