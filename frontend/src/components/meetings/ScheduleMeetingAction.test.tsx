import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ScheduleMeetingAction, { __testing } from './ScheduleMeetingAction'
import type { Meeting } from '../../types/meeting'

const baseMeeting: Meeting = {
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

function apiError(status: number, detail: string): Error {
  return Object.assign(new Error(detail), { name: 'ApiError', status })
}

describe('ScheduleMeetingAction', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the "Schedule meeting" button by default', () => {
    render(<ScheduleMeetingAction applicationId={5} />)

    expect(screen.getByTestId('schedule-meeting-open-5')).toBeInTheDocument()
  })

  it('hides the schedule controls in readOnly mode', () => {
    render(<ScheduleMeetingAction applicationId={5} readOnly />)

    expect(screen.queryByTestId('schedule-meeting-open-5')).not.toBeInTheDocument()
    expect(screen.queryByTestId('schedule-meeting-form-5')).not.toBeInTheDocument()
  })

  it('opens the form pre-populated with defaults', async () => {
    render(<ScheduleMeetingAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('schedule-meeting-open-5'))

    expect(screen.getByTestId('schedule-meeting-form-5')).toBeInTheDocument()
    const durationSelect = screen.getByTestId('schedule-meeting-duration-5') as HTMLSelectElement
    expect(durationSelect.value).toBe('30')
  })

  it('submit empty form rejects before hitting the API', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch
    render(<ScheduleMeetingAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('schedule-meeting-open-5'))
    // Bypass native HTML validation to exercise our JS-side guard.
    const form = screen.getByTestId('schedule-meeting-form-5') as HTMLFormElement
    form.noValidate = true
    await userEvent.click(screen.getByTestId('schedule-meeting-submit-5'))

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByTestId('schedule-meeting-error-5')).toHaveTextContent(
      /date and time/i,
    )
  })

  it('submits the picked date/time/duration/location/notes via the API', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => baseMeeting,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const onScheduled = vi.fn()
    render(<ScheduleMeetingAction applicationId={5} onScheduled={onScheduled} />)
    await userEvent.click(screen.getByTestId('schedule-meeting-open-5'))

    // 2026-05-01T09:30 (local time) -- toISOString() in the browser
    // converts to a UTC timestamp.
    await userEvent.type(
      screen.getByTestId('schedule-meeting-when-5'),
      '2026-05-01T09:30',
    )
    await userEvent.selectOptions(
      screen.getByTestId('schedule-meeting-duration-5'),
      '45',
    )
    await userEvent.type(
      screen.getByTestId('schedule-meeting-location-5'),
      'Room 2',
    )
    await userEvent.type(
      screen.getByTestId('schedule-meeting-notes-5'),
      'Bring docs',
    )

    await userEvent.click(screen.getByTestId('schedule-meeting-submit-5'))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0]
    expect(init?.method).toBe('POST')
    const body = JSON.parse((init as RequestInit | undefined)?.body as string)
    expect(body.duration_minutes).toBe(45)
    expect(body.location).toBe('Room 2')
    expect(body.notes).toBe('Bring docs')
    expect(typeof body.scheduled_at).toBe('string')
    expect(body.scheduled_at).toMatch(/^\d{4}-\d{2}-\d{2}T/)
    expect(body.scheduled_at.endsWith('Z')).toBe(true)

    expect(await screen.findByTestId('schedule-meeting-success-5')).toBeInTheDocument()
    expect(onScheduled).toHaveBeenCalledWith(5, baseMeeting)
  })

  it('sends null location / notes when left empty', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => baseMeeting,
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<ScheduleMeetingAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('schedule-meeting-open-5'))

    await userEvent.type(
      screen.getByTestId('schedule-meeting-when-5'),
      '2026-05-01T09:30',
    )

    await userEvent.click(screen.getByTestId('schedule-meeting-submit-5'))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const body = JSON.parse((fetchMock.mock.calls[0]?.[1]?.body ?? '{}') as string)
    expect(body.location).toBeNull()
    expect(body.notes).toBeNull()
  })

  it('maps a 422 backend detail to a readable error and keeps the form open', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'duration_minutes must be > 0' }),
    }) as typeof fetch

    render(<ScheduleMeetingAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('schedule-meeting-open-5'))
    await userEvent.type(
      screen.getByTestId('schedule-meeting-when-5'),
      '2026-05-01T09:30',
    )
    await userEvent.click(screen.getByTestId('schedule-meeting-submit-5'))

    expect(await screen.findByTestId('schedule-meeting-error-5')).toHaveTextContent(
      /duration_minutes must be > 0/i,
    )
    expect(screen.getByTestId('schedule-meeting-form-5')).toBeInTheDocument()
  })

  it('maps a 403 backend detail to a permission-specific error', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    render(<ScheduleMeetingAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('schedule-meeting-open-5'))
    await userEvent.type(
      screen.getByTestId('schedule-meeting-when-5'),
      '2026-05-01T09:30',
    )
    await userEvent.click(screen.getByTestId('schedule-meeting-submit-5'))

    expect(await screen.findByTestId('schedule-meeting-error-5')).toHaveTextContent(
      /permission/i,
    )
  })

  it('maps a 404 backend detail to an application-not-available error', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Application not found' }),
    }) as typeof fetch

    render(<ScheduleMeetingAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('schedule-meeting-open-5'))
    await userEvent.type(
      screen.getByTestId('schedule-meeting-when-5'),
      '2026-05-01T09:30',
    )
    await userEvent.click(screen.getByTestId('schedule-meeting-submit-5'))

    expect(await screen.findByTestId('schedule-meeting-error-5')).toHaveTextContent(
      /no longer available/i,
    )
  })

  it('maps an ApiError thrown by a parent with isApiError check', () => {
    // ``__testing.describeError`` exposes the same mapping used internally
    // so unit tests can exercise edge cases without re-rendering.
    expect(__testing.describeError(apiError(401, 'whatever'))).toMatch(/session/i)
    expect(__testing.describeError(apiError(403, 'whatever'))).toMatch(/permission/i)
    expect(__testing.describeError(apiError(404, 'whatever'))).toMatch(/available/i)
    expect(__testing.describeError(apiError(422, 'Bad'))).toBe('Bad')
    expect(__testing.describeError(apiError(500, 'x'))).toBe(
      'Failed to schedule the meeting',
    )
    expect(__testing.describeError(new Error('not an api error'))).toBe(
      'Failed to schedule the meeting',
    )
  })

  it('cancel closes the form without calling the API', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    render(<ScheduleMeetingAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('schedule-meeting-open-5'))
    await userEvent.type(
      screen.getByTestId('schedule-meeting-when-5'),
      '2026-05-01T09:30',
    )
    await userEvent.click(screen.getByTestId('schedule-meeting-cancel-5'))

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByTestId('schedule-meeting-form-5')).not.toBeInTheDocument()
    expect(screen.getByTestId('schedule-meeting-open-5')).toBeInTheDocument()
  })

  it('localDateTimeToIsoUtc converts a local datetime to UTC ISO 8601', () => {
    const result = __testing.localDateTimeToIsoUtc('2026-05-01T09:30')
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/)
  })

  it('localDateTimeToIsoUtc returns null for invalid input', () => {
    expect(__testing.localDateTimeToIsoUtc('not-a-date')).toBeNull()
  })

  it('describeMeeting renders a human-readable summary', () => {
    const summary = __testing.describeMeeting(baseMeeting)
    // The locale string differs across CI environments (e.g. "5/1/2026,
    // 9:30:00 AM" on en-US, "1/5/2026, 09:30:00" on en-GB). Match on
    // shape so the assertion does not flake.
    expect(summary).toContain('30 min')
    expect(summary).toContain('Room 2')
  })
})
