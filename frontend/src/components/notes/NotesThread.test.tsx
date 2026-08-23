import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import NotesThread from './NotesThread'
import type { Note } from '../../types/note'

const baseNote: Note = {
  id: 1,
  tenant_id: 10,
  student_id: 42,
  application_id: 5,
  author_user_id: 7,
  body: 'Spoke with student about program options.',
  created_at: '2026-04-01T09:00:00Z',
  updated_at: '2026-04-01T09:00:00Z',
}

function makeFetch(handler: (path: string, init?: RequestInit) => Promise<Response>) {
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = typeof url === 'string' ? url : url.toString()
    return handler(path, init)
  }) as unknown as typeof fetch
}

describe('NotesThread', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the loading state on first paint', () => {
    let resolveJson!: (value: Response) => void
    globalThis.fetch = vi.fn().mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveJson = resolve
        }),
    ) as typeof fetch
    render(<NotesThread applicationId={5} studentId={42} currentUserId={7} />)
    expect(screen.getByTestId('notes-loading-5')).toBeInTheDocument()
    // Resolve to avoid an unhandled rejection.
    void resolveJson({ ok: true, status: 200, json: async () => [] } as Response)
  })

  it('renders the empty state when the application has no notes', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/notes') && path.includes('application_id=5')) {
        return { ok: true, status: 200, json: async () => [] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<NotesThread applicationId={5} studentId={42} currentUserId={7} />)
    expect(await screen.findByTestId('notes-empty-5')).toHaveTextContent(
      /no internal notes/i,
    )
  })

  it('renders one row per note', async () => {
    const notes: Note[] = [
      baseNote,
      {
        ...baseNote,
        id: 2,
        body: 'Follow-up scheduled for next week.',
      },
    ]
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/notes') && path.includes('application_id=5')) {
        return { ok: true, status: 200, json: async () => notes } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<NotesThread applicationId={5} studentId={42} currentUserId={7} />)
    expect(await screen.findByTestId('notes-list-5')).toBeInTheDocument()
    expect(screen.getByTestId('note-row-1')).toHaveTextContent(
      'Spoke with student about program options.',
    )
    expect(screen.getByTestId('note-row-2')).toHaveTextContent(
      'Follow-up scheduled for next week.',
    )
  })

  it('renders a permission error on 403', async () => {
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    } as unknown as Response))

    render(<NotesThread applicationId={5} studentId={42} currentUserId={7} />)
    expect(await screen.findByTestId('notes-error-5')).toHaveTextContent(
      /permission/i,
    )
  })

  it('hides the add-note form in readOnly mode', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/notes')) {
        return { ok: true, status: 200, json: async () => [baseNote] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<NotesThread applicationId={5} studentId={42} currentUserId={7} readOnly />)
    expect(await screen.findByTestId('notes-list-5')).toBeInTheDocument()
    expect(screen.queryByTestId('add-note-open-5')).not.toBeInTheDocument()
  })

  it('shows the add-note form when not readOnly and studentId is set', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/notes')) {
        return { ok: true, status: 200, json: async () => [] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<NotesThread applicationId={5} studentId={42} currentUserId={7} />)
    expect(await screen.findByTestId('notes-empty-5')).toBeInTheDocument()
    expect(screen.getByTestId('add-note-open-5')).toBeInTheDocument()
  })

  it('hides the add-note form when studentId is null', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/notes')) {
        return { ok: true, status: 200, json: async () => [] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<NotesThread applicationId={5} studentId={null} currentUserId={7} />)
    expect(await screen.findByTestId('notes-empty-5')).toBeInTheDocument()
    expect(screen.queryByTestId('add-note-open-5')).not.toBeInTheDocument()
  })

  it('reload button triggers a fresh fetch', async () => {
    let calls = 0
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/notes') && path.includes('application_id=5')) {
        calls += 1
        return { ok: true, status: 200, json: async () => [baseNote] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<NotesThread applicationId={5} studentId={42} currentUserId={7} />)
    await screen.findByTestId('notes-list-5')
    await userEvent.click(screen.getByTestId('notes-reload-5'))
    expect(calls).toBeGreaterThanOrEqual(2)
  })
})
