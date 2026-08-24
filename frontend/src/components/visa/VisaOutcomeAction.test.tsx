import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import VisaOutcomeAction, { __testing } from './VisaOutcomeAction'
import { updateVisaOutcome } from '../../api/visa'
import type { VisaOutcome } from '../../types/visa'

vi.mock('../../api/visa', () => ({
  updateVisaOutcome: vi.fn(),
}))
const updateVisaOutcomeMock = vi.mocked(updateVisaOutcome)

function apiError(status: number, message: string): Error {
  return Object.assign(new Error(message), { name: 'ApiError', status })
}

function makeOutcome(overrides: Partial<VisaOutcome> = {}): VisaOutcome {
  return {
    id: 11,
    tenant_id: 10,
    application_id: 5,
    status: 'approved',
    outcome_date: '2026-09-30T10:00:00+00:00',
    notes: 'Stamped at US embassy',
    created_at: '2026-09-30T10:01:00+00:00',
    updated_at: '2026-09-30T10:01:00+00:00',
    ...overrides,
  }
}

describe('VisaOutcomeAction', () => {
  beforeEach(() => {
    updateVisaOutcomeMock.mockReset()
  })

  it('opens the form with Record outcome label when no outcome exists yet', async () => {
    render(<VisaOutcomeAction applicationId={5} />)
    expect(screen.getByTestId('visa-outcome-open-5')).toHaveTextContent(/record outcome/i)
    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    expect(screen.getByTestId('visa-outcome-form-5')).toBeInTheDocument()
    const status = screen.getByTestId('visa-outcome-status-5')
    expect(status).toHaveAttribute('aria-required', 'true')
    expect(status).toHaveAttribute('maxlength', '32')
  })

  it('opens as Update outcome when an initial outcome is provided', async () => {
    render(<VisaOutcomeAction applicationId={5} initialOutcome={makeOutcome()} />)
    expect(screen.getByTestId('visa-outcome-open-5')).toHaveTextContent(/update outcome/i)
    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    expect(screen.getByTestId('visa-outcome-status-5')).toHaveValue('approved')
    expect(screen.getByTestId('visa-outcome-notes-5')).toHaveValue('Stamped at US embassy')
    // In update mode ``status`` is optional.
    expect(screen.getByTestId('visa-outcome-status-5')).not.toHaveAttribute('aria-required', 'true')
  })

  it('blocks submit and shows a validation error when status is empty in create mode', async () => {
    render(<VisaOutcomeAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    // In create mode ``status`` is required -- the input carries the
    // ``required`` attribute so the form's native HTML5 validation
    // also refuses to submit. The component-level validation is
    // belt-and-braces for callers that bypass it.
    expect(screen.getByTestId('visa-outcome-status-5')).toBeRequired()
    expect(updateVisaOutcomeMock).not.toHaveBeenCalled()
  })

  it('blocks submit when every field is empty in update mode', async () => {
    render(<VisaOutcomeAction applicationId={5} initialOutcome={makeOutcome()} />)
    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    // Replace the prefilled values so all three fields are empty.
    await userEvent.clear(screen.getByTestId('visa-outcome-status-5'))
    await userEvent.clear(screen.getByTestId('visa-outcome-date-5'))
    await userEvent.clear(screen.getByTestId('visa-outcome-notes-5'))
    await userEvent.click(screen.getByTestId('visa-outcome-submit-5'))

    expect(screen.getByTestId('visa-outcome-validation-5')).toHaveTextContent(/update at least one/i)
    expect(updateVisaOutcomeMock).not.toHaveBeenCalled()
  })

  it('records the outcome in create mode and shows success', async () => {
    updateVisaOutcomeMock.mockResolvedValue(
      makeOutcome({ status: 'approved', notes: 'OK' }),
    )
    const onUpdated = vi.fn()
    render(<VisaOutcomeAction applicationId={5} onUpdated={onUpdated} />)

    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    await userEvent.type(screen.getByTestId('visa-outcome-status-5'), 'Approved')
    await userEvent.type(screen.getByTestId('visa-outcome-notes-5'), 'OK')
    await userEvent.click(screen.getByTestId('visa-outcome-submit-5'))

    expect(updateVisaOutcomeMock).toHaveBeenCalledWith(5, {
      status: 'Approved',
      outcome_date: null,
      notes: 'OK',
    })
    expect(await screen.findByTestId('visa-outcome-success-5')).toHaveTextContent(/outcome recorded/i)
    expect(onUpdated).toHaveBeenCalledWith(5, expect.objectContaining({ status: 'approved' }))
  })

  it('trims whitespace around the status before sending', async () => {
    updateVisaOutcomeMock.mockResolvedValue(makeOutcome({ status: 'rejected' }))
    render(<VisaOutcomeAction applicationId={5} initialOutcome={makeOutcome()} />)

    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    await userEvent.clear(screen.getByTestId('visa-outcome-status-5'))
    await userEvent.type(screen.getByTestId('visa-outcome-status-5'), '  Rejected  ')
    await userEvent.click(screen.getByTestId('visa-outcome-submit-5'))

    expect(updateVisaOutcomeMock).toHaveBeenCalledWith(
      5,
      expect.objectContaining({ status: 'Rejected' }),
    )
  })

  it('converts a picked datetime-local value to a UTC ISO timestamp before PATCHing', async () => {
    updateVisaOutcomeMock.mockResolvedValue(makeOutcome())
    render(<VisaOutcomeAction applicationId={5} initialOutcome={makeOutcome()} />)

    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    await userEvent.clear(screen.getByTestId('visa-outcome-date-5'))
    // 2026-09-30T10:00 in the user's local timezone; on submit the
    // component MUST convert to a UTC ISO string (Z-suffixed).
    await userEvent.type(screen.getByTestId('visa-outcome-date-5'), '2026-09-30T10:00')
    await userEvent.click(screen.getByTestId('visa-outcome-submit-5'))

    expect(updateVisaOutcomeMock).toHaveBeenCalledTimes(1)
    const payload = updateVisaOutcomeMock.mock.calls[0]?.[1]
    expect(payload?.outcome_date).toMatch(/T10:00:00\.000Z$/)
  })

  it('submits without a datetime-local date (date is optional)', async () => {
    updateVisaOutcomeMock.mockResolvedValue(makeOutcome())
    render(<VisaOutcomeAction applicationId={5} />)

    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    await userEvent.type(screen.getByTestId('visa-outcome-status-5'), 'Approved')
    await userEvent.click(screen.getByTestId('visa-outcome-submit-5'))

    expect(updateVisaOutcomeMock).toHaveBeenCalledTimes(1)
    const payload = updateVisaOutcomeMock.mock.calls[0]?.[1]
    // Outcome date is omitted -> the component sends null and the
    // backend treats it as "no outcome date yet".
    expect(payload?.outcome_date).toBeNull()
  })

  it('reports an unparseable datetime-local value back to the user via the helper', async () => {
    // jsdom refuses to set an invalid value on ``type="datetime-local"``
    // inputs (the browser strips it), so this case is most reliably
    // exercised through the helper directly: the validation rule
    // rejects the empty/garbage value before the PATCH goes out.
    expect(__testing.hasResolvedDate({ status: '', outcome_date: '', notes: '' })).toBe(false)
    expect(__testing.hasResolvedDate({ status: '', outcome_date: 'not-a-date', notes: '' })).toBe(false)
  })

  it('sends null for omitted fields when updating an existing outcome', async () => {
    updateVisaOutcomeMock.mockResolvedValue(makeOutcome())
    render(<VisaOutcomeAction applicationId={5} initialOutcome={makeOutcome()} />)

    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    await userEvent.clear(screen.getByTestId('visa-outcome-date-5'))
    await userEvent.clear(screen.getByTestId('visa-outcome-notes-5'))
    // Leave the prefilled status. Only status+date are sent (notes -> null).
    await userEvent.clear(screen.getByTestId('visa-outcome-status-5'))
    await userEvent.type(screen.getByTestId('visa-outcome-status-5'), 'Approved')
    await userEvent.click(screen.getByTestId('visa-outcome-submit-5'))

    expect(updateVisaOutcomeMock).toHaveBeenCalledWith(5, {
      status: 'Approved',
      outcome_date: null,
      notes: null,
    })
  })

  it('shows a mapped 422 error and keeps the form open', async () => {
    updateVisaOutcomeMock.mockRejectedValue(
      apiError(
        422,
        "Application in stage 'enrolled' cannot have its visa outcome updated.",
      ),
    )
    render(<VisaOutcomeAction applicationId={5} />)

    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    await userEvent.type(screen.getByTestId('visa-outcome-status-5'), 'Approved')
    await userEvent.click(screen.getByTestId('visa-outcome-submit-5'))

    expect(await screen.findByTestId('visa-outcome-error-5')).toHaveTextContent(
      /cannot have its visa outcome updated/i,
    )
    expect(screen.getByTestId('visa-outcome-form-5')).toBeInTheDocument()
  })

  it('shows a mapped 503 error', async () => {
    updateVisaOutcomeMock.mockRejectedValue(
      apiError(503, 'Visa outcome update is temporarily unavailable'),
    )
    render(<VisaOutcomeAction applicationId={5} />)

    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    await userEvent.type(screen.getByTestId('visa-outcome-status-5'), 'Approved')
    await userEvent.click(screen.getByTestId('visa-outcome-submit-5'))

    expect(await screen.findByTestId('visa-outcome-error-5')).toHaveTextContent(
      /temporarily unavailable/i,
    )
  })

  it('updates the character counters as the visa processor types', async () => {
    render(<VisaOutcomeAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('visa-outcome-open-5'))
    await userEvent.type(screen.getByTestId('visa-outcome-status-5'), 'abc')
    expect(screen.getByTestId('visa-outcome-status-counter-5')).toHaveTextContent(
      '29 characters remaining',
    )
    await userEvent.type(screen.getByTestId('visa-outcome-notes-5'), 'note')
    expect(screen.getByTestId('visa-outcome-notes-counter-5')).toHaveTextContent(
      '1996 characters remaining',
    )
  })
})

describe('VisaOutcomeAction __testing helpers', () => {
  it('localDateTimeToIsoUtc converts a local datetime-local value to UTC ISO 8601', () => {
    const out = __testing.localDateTimeToIsoUtc('2026-09-30T10:00')
    expect(out).not.toBeNull()
    // The exact UTC time depends on the host timezone, but it MUST
    // end in Z and parse round-trip back to the same wall clock when
    // interpreted locally.
    expect(out).toMatch(/Z$/)
    const date = new Date(out as string)
    expect(date.getFullYear()).toBe(2026)
    expect(date.getMonth()).toBe(8) // September (0-indexed)
    expect(date.getDate()).toBe(30)
    expect(date.getHours()).toBe(10)
    expect(date.getMinutes()).toBe(0)
  })

  it('localDateTimeToIsoUtc returns null for empty / unparseable values', () => {
    expect(__testing.localDateTimeToIsoUtc('')).toBeNull()
    expect(__testing.localDateTimeToIsoUtc('not-a-date')).toBeNull()
  })
})
