import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createNote, deleteNote, getNote, listNotes, updateNote } from './notes'
import type { Note } from '../types/note'

const note: Note = {
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

describe('notes API client', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('listNotes issues GET /notes with no query when no filters are passed', async () => {
    const fetchMock = makeFetch(async (path, init) => {
      expect(init?.method ?? 'GET').toBe('GET')
      expect(path).toContain('/notes')
      return { ok: true, status: 200, json: async () => [note] } as Response
    })
    globalThis.fetch = fetchMock

    const result = await listNotes()
    expect(result).toEqual([note])
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('listNotes serializes the application_id filter', async () => {
    let capturedPath = ''
    globalThis.fetch = makeFetch(async (path) => {
      capturedPath = path
      return { ok: true, status: 200, json: async () => [note] } as Response
    })

    await listNotes({ application_id: 5 })
    expect(capturedPath).toContain('/notes?')
    expect(capturedPath).toContain('application_id=5')
  })

  it('listNotes serializes both student_id and application_id filters', async () => {
    let capturedPath = ''
    globalThis.fetch = makeFetch(async (path) => {
      capturedPath = path
      return { ok: true, status: 200, json: async () => [note] } as Response
    })

    await listNotes({ student_id: 42, application_id: 5 })
    expect(capturedPath).toContain('student_id=42')
    expect(capturedPath).toContain('application_id=5')
  })

  it('getNote issues GET /notes/{id}', async () => {
    let capturedPath = ''
    globalThis.fetch = makeFetch(async (path) => {
      capturedPath = path
      return { ok: true, status: 200, json: async () => note } as Response
    })

    await getNote(1)
    expect(capturedPath).toContain('/notes/1')
  })

  it('createNote issues POST /notes with the JSON body', async () => {
    let capturedPath = ''
    let capturedInit: RequestInit | undefined
    globalThis.fetch = makeFetch(async (path, init) => {
      capturedPath = path
      capturedInit = init
      return { ok: true, status: 201, json: async () => note } as Response
    })

    await createNote({
      student_id: 42,
      application_id: 5,
      body: 'Hello, world.',
    })
    expect(capturedPath).toContain('/notes')
    expect(capturedInit?.method).toBe('POST')
    expect(JSON.parse((capturedInit?.body ?? '{}') as string)).toEqual({
      student_id: 42,
      application_id: 5,
      body: 'Hello, world.',
    })
  })

  it('updateNote issues PATCH /notes/{id} with the JSON body', async () => {
    let capturedPath = ''
    let capturedInit: RequestInit | undefined
    globalThis.fetch = makeFetch(async (path, init) => {
      capturedPath = path
      capturedInit = init
      return { ok: true, status: 200, json: async () => note } as Response
    })

    await updateNote(1, { body: 'Edited.' })
    expect(capturedPath).toContain('/notes/1')
    expect(capturedInit?.method).toBe('PATCH')
    expect(JSON.parse((capturedInit?.body ?? '{}') as string)).toEqual({
      body: 'Edited.',
    })
  })

  it('deleteNote issues DELETE /notes/{id}', async () => {
    let capturedPath = ''
    let capturedInit: RequestInit | undefined
    globalThis.fetch = makeFetch(async (path, init) => {
      capturedPath = path
      capturedInit = init
      // 204 No Content
      return { ok: true, status: 204, json: async () => undefined } as Response
    })

    await deleteNote(1)
    expect(capturedPath).toContain('/notes/1')
    expect(capturedInit?.method).toBe('DELETE')
  })
})
