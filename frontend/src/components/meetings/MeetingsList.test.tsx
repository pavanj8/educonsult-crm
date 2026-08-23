import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MeetingsList from './MeetingsList'
import type { Meeting } from '../../types/meeting'

const meetings: Meeting[] = [
  {
    id: 99,
    tenant_id: 10,
    application_id: 5,
    counselor_id: 7,
    student_id: 42,
    scheduled_at: '2026-05-01T09:30:00Z',
    duration_minutes: 30,
    location: 'Room 2',
    notes: 'Bring documents',
    created_at: '2026-04-01T09:00:00Z',
    updated_at: '2026-04-01T09:00:00Z',
  },
  {
    id: 100,
    tenant_id: 10,
    application_id: 5,
    counselor_id: 7,
    student_id: 42,
    scheduled_at: '2026-05-08T11:00:00Z',
    duration_minutes: 45,
    location: null,
    notes: null,
    created_at: '2026-04-01T09:00:00Z',
    updated_at: '2026-04-01T09:00:00Z',
  },
]

function makeFetch(handler: (path: string) => Promise<Response>) {
  return vi.fn(async (url: RequestInfo | URL) => {
    const path = typeof url === 'string' ? url : url.toString()
    return handler(path)
  }) as unknown as typeof fetch
}

describe('MeetingsList', () => {
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
    render(<MeetingsList applicationId={5} />)
    expect(screen.getByTestId('meetings-loading-5')).toBeInTheDocument()
    // Resolve to avoid an unhandled rejection.
    void resolveJson({ ok: true, status: 200, json: async () => meetings } as Response)
  })

  it('renders an empty state when the application has no meetings', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/applications/5/meetings')) {
        return { ok: true, status: 200, json: async () => [] } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })
    render(<MeetingsList applicationId={5} />)
    expect(await screen.findByTestId('meetings-empty-5')).toHaveTextContent(
      /no meetings/i,
    )
  })

  it('renders one row per meeting', async () => {
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/applications/5/meetings')) {
        return { ok: true, status: 200, json: async () => meetings } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<MeetingsList applicationId={5} />)
    expect(await screen.findByTestId('meetings-list-5')).toBeInTheDocument()
    expect(screen.getByTestId('meeting-row-99')).toHaveTextContent('Bring documents')
    expect(screen.getByTestId('meeting-row-100')).toHaveTextContent('—')
  })

  it('renders an error state on 403', async () => {
    globalThis.fetch = makeFetch(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    } as unknown as Response))
    render(<MeetingsList applicationId={5} />)
    expect(await screen.findByTestId('meetings-error-5')).toHaveTextContent(
      /permission/i,
    )
  })

  it('reload button triggers a fresh fetch', async () => {
    let calls = 0
    globalThis.fetch = makeFetch(async (path) => {
      if (path.includes('/applications/5/meetings')) {
        calls += 1
        return { ok: true, status: 200, json: async () => meetings } as Response
      }
      throw new Error(`unexpected fetch: ${path}`)
    })

    render(<MeetingsList applicationId={5} />)
    await screen.findByTestId('meetings-list-5')
    await userEvent.click(screen.getByTestId('meetings-reload-5'))
    expect(calls).toBeGreaterThanOrEqual(2)
  })
})
