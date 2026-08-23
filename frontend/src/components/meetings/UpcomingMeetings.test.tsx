import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import UpcomingMeetings from './UpcomingMeetings'

const futureIso = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
const soonerIso = new Date(Date.now() + 60 * 60 * 1000).toISOString()
const pastIso = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()

const baseMeeting = {
  id: 99,
  tenant_id: 10,
  application_id: 5,
  counselor_id: 7,
  student_id: 42,
  scheduled_at: futureIso,
  duration_minutes: 30,
  location: 'Room 2',
  notes: 'Bring documents',
  created_at: '2026-04-01T09:00:00Z',
  updated_at: '2026-04-01T09:00:00Z',
}

function makeFetch(handler: (path: string) => Promise<Response>) {
  return vi.fn(async (url: RequestInfo | URL) => {
    const path = typeof url === 'string' ? url : url.toString()
    return handler(path)
  }) as unknown as typeof fetch
}

describe('UpcomingMeetings', () => {
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
    render(<UpcomingMeetings />)
    expect(screen.getByTestId('upcoming-meetings-loading')).toBeInTheDocument()
    // Resolve to avoid an unhandled rejection.
    void resolveJson({ ok: true, status: 200, json: async () => [] } as Response)
  })

  it('renders an empty state when the student has no upcoming meetings', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.endsWith('/me/meetings')) {
        return { ok: true, status: 200, json: async () => [] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })
    render(<UpcomingMeetings />)
    expect(await screen.findByTestId('upcoming-meetings-empty')).toHaveTextContent(
      /no upcoming meetings/i,
    )
  })

  it('hides past meetings and renders one row per upcoming meeting', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.endsWith('/me/meetings')) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            { ...baseMeeting, id: 1, scheduled_at: futureIso },
            { ...baseMeeting, id: 2, scheduled_at: pastIso },
            { ...baseMeeting, id: 3, scheduled_at: soonerIso },
          ],
        } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<UpcomingMeetings />)
    expect(await screen.findByTestId('upcoming-meetings-list')).toBeInTheDocument()
    expect(screen.getByTestId('upcoming-meeting-1')).toBeInTheDocument()
    expect(screen.getByTestId('upcoming-meeting-3')).toBeInTheDocument()
    expect(screen.queryByTestId('upcoming-meeting-2')).not.toBeInTheDocument()
    // Location + notes are surfaced for the populated row.
    expect(screen.getByTestId('upcoming-meeting-1')).toHaveTextContent('Room 2')
    expect(screen.getByTestId('upcoming-meeting-1')).toHaveTextContent('Bring documents')
    expect(screen.getByTestId('upcoming-meeting-1')).toHaveTextContent(/30 min/)
  })

  it('omits the location/notes rows when they are null', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.endsWith('/me/meetings')) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            { ...baseMeeting, id: 5, location: null, notes: null },
          ],
        } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<UpcomingMeetings />)
    expect(await screen.findByTestId('upcoming-meeting-5')).toBeInTheDocument()
    expect(screen.queryByText(/Location:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Notes:/)).not.toBeInTheDocument()
  })

  it('renders an error state on 403', async () => {
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    } as unknown as Response))
    render(<UpcomingMeetings />)
    expect(await screen.findByTestId('upcoming-meetings-error')).toHaveTextContent(
      /permission/i,
    )
  })

  it('reload button triggers a fresh fetch', async () => {
    let calls = 0
    globalThis.fetch = makeFetch(async (path) => {
      if (path.endsWith('/me/meetings')) {
        calls += 1
        return { ok: true, status: 200, json: async () => [baseMeeting] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<UpcomingMeetings />)
    await screen.findByTestId('upcoming-meetings-list')
    await userEvent.click(screen.getByTestId('upcoming-meetings-reload'))
    expect(calls).toBeGreaterThanOrEqual(2)
  })
})