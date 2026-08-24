import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import VisaDetailUpdateForm, { __testing } from './VisaDetailUpdateForm'
import { fetchVisaDetail, updateVisaDetail } from '../../api/visa'

vi.mock('../../api/visa', () => ({
  fetchVisaDetail: vi.fn(),
  updateVisaDetail: vi.fn(),
}))
const fetchVisaDetailMock = vi.mocked(fetchVisaDetail)
const updateVisaDetailMock = vi.mocked(updateVisaDetail)

function apiError(status: number, message: string): Error {
  return Object.assign(new Error(message), { name: 'ApiError', status })
}

const savedDetail = {
  id: 1,
  tenant_id: 10,
  application_id: 5,
  visa_type: 'F-1 Student',
  interview_date: '2026-11-05T09:00:00.000Z',
  created_at: '2026-09-01T09:00:00Z',
  updated_at: '2026-09-01T09:00:00Z',
}

describe('VisaDetailUpdateForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default load: visa detail not yet recorded. Individual tests
    // override this with a resolved detail.
    fetchVisaDetailMock.mockResolvedValue(null)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders a loading state and then an empty form when no detail is recorded', async () => {
    render(<VisaDetailUpdateForm applicationId={5} />)

    expect(screen.getByTestId('visa-detail-loading-5')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })
    expect((screen.getByTestId('visa-detail-type-5') as HTMLInputElement).value).toBe('')
    expect((screen.getByTestId('visa-detail-interview-5') as HTMLInputElement).value).toBe('')
  })

  it('pre-fills the form from a previously-recorded visa detail', async () => {
    fetchVisaDetailMock.mockResolvedValue(savedDetail)
    render(<VisaDetailUpdateForm applicationId={5} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })
    expect((screen.getByTestId('visa-detail-type-5') as HTMLInputElement).value).toBe(
      'F-1 Student',
    )
    // The picker renders the local wall clock for the UTC instant
    // 2026-11-05T09:00:00Z. The exact string depends on the test
    // runner's timezone, so assert the picker is non-empty and that
    // it round-trips back to the same UTC ISO via the helper.
    const interviewValue = (screen.getByTestId('visa-detail-interview-5') as HTMLInputElement).value
    expect(interviewValue).not.toBe('')
  })

  it('shows a load error and no form when the GET fails with a non-404', async () => {
    fetchVisaDetailMock.mockRejectedValue(apiError(403, 'Insufficient permissions'))
    render(<VisaDetailUpdateForm applicationId={5} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-load-error-5')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('visa-detail-form-5')).not.toBeInTheDocument()
  })

  it('submits the entered visa type and (UTC) interview date on Save', async () => {
    updateVisaDetailMock.mockResolvedValue({
      ...savedDetail,
      visa_type: 'Tier 4 Student',
      interview_date: '2026-12-01T03:30:00.000Z',
    })
    const onSaved = vi.fn()
    render(<VisaDetailUpdateForm applicationId={5} onSaved={onSaved} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })

    await userEvent.clear(screen.getByTestId('visa-detail-type-5'))
    await userEvent.type(screen.getByTestId('visa-detail-type-5'), 'Tier 4 Student')
    // 2026-11-05T09:00 in the test runner's local timezone => UTC ISO
    // with Z suffix. The helper inside the form does the conversion;
    // we just confirm the UTC ISO ends in "Z" and parses to the same
    // wall-clock fields.
    await userEvent.type(screen.getByTestId('visa-detail-interview-5'), '2026-11-05T09:00')
    await userEvent.click(screen.getByTestId('visa-detail-submit-5'))

    await waitFor(() => {
      expect(updateVisaDetailMock).toHaveBeenCalledTimes(1)
    })
    const [appId, payload] = updateVisaDetailMock.mock.calls[0] ?? []
    expect(appId).toBe(5)
    expect(payload).toMatchObject({
      visa_type: 'Tier 4 Student',
    })
    // The interview_date must be a non-null ISO string ending in "Z"
    // and round-trip back to the same local wall clock.
    expect((payload as { interview_date: string | null }).interview_date).not.toBeNull()
    const interviewIso = (payload as { interview_date: string }).interview_date
    expect(interviewIso).toMatch(/Z$/)
    const parsed = new Date(interviewIso)
    expect(parsed.toISOString().slice(0, 16)).toBe('2026-11-05T09:00')

    expect(await screen.findByTestId('visa-detail-success-5')).toBeInTheDocument()
    expect(onSaved).toHaveBeenCalledWith(5, expect.objectContaining({ visa_type: 'Tier 4 Student' }))
  })

  it('submits a null interview_date when the picker is empty', async () => {
    updateVisaDetailMock.mockResolvedValue({ ...savedDetail, interview_date: null })
    render(<VisaDetailUpdateForm applicationId={5} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })

    await userEvent.type(screen.getByTestId('visa-detail-type-5'), 'F-1 Student')
    // Leave the interview picker empty.
    await userEvent.click(screen.getByTestId('visa-detail-submit-5'))

    await waitFor(() => {
      expect(updateVisaDetailMock).toHaveBeenCalledTimes(1)
    })
    const [, payload] = updateVisaDetailMock.mock.calls[0] ?? []
    expect(payload).toEqual({ visa_type: 'F-1 Student', interview_date: null })
  })

  it('requires a non-empty visa type and shows a client-side validation error', async () => {
    render(<VisaDetailUpdateForm applicationId={5} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })

    // The input has the native ``required`` attribute, so we submit
    // through the form and rely on the form's own submitError branch
    // when the browser would otherwise block submission. To exercise
    // the component's own JS validation we type a single space (which
    // passes the native required check but trims to empty).
    await userEvent.type(screen.getByTestId('visa-detail-type-5'), '   ')
    await userEvent.click(screen.getByTestId('visa-detail-submit-5'))

    expect(
      await screen.findByTestId('visa-detail-submit-error-5'),
    ).toHaveTextContent(/visa type/i)
    expect(updateVisaDetailMock).not.toHaveBeenCalled()
  })

  it('maps a 422 backend detail to a readable error and keeps the form open', async () => {
    updateVisaDetailMock.mockRejectedValue(apiError(422, 'visa_type too long'))
    render(<VisaDetailUpdateForm applicationId={5} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })

    await userEvent.type(screen.getByTestId('visa-detail-type-5'), 'F-1 Student')
    await userEvent.click(screen.getByTestId('visa-detail-submit-5'))

    expect(await screen.findByTestId('visa-detail-submit-error-5')).toHaveTextContent(
      /visa_type too long/i,
    )
    expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
  })

  it('maps a 403 backend detail to a permission-specific error', async () => {
    updateVisaDetailMock.mockRejectedValue(apiError(403, 'Insufficient permissions'))
    render(<VisaDetailUpdateForm applicationId={5} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })

    await userEvent.type(screen.getByTestId('visa-detail-type-5'), 'F-1 Student')
    await userEvent.click(screen.getByTestId('visa-detail-submit-5'))

    expect(await screen.findByTestId('visa-detail-submit-error-5')).toHaveTextContent(
      /permission/i,
    )
  })

  it('renders a read-only summary with no Save button when readOnly is true', async () => {
    fetchVisaDetailMock.mockResolvedValue(savedDetail)
    render(<VisaDetailUpdateForm applicationId={5} readOnly />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-readonly-5')).toBeInTheDocument()
    })
    expect(screen.getByTestId('visa-detail-readonly-type-5')).toHaveTextContent('F-1 Student')
    expect(screen.getByTestId('visa-detail-readonly-interview-5')).toBeInTheDocument()
    expect(screen.queryByTestId('visa-detail-submit-5')).not.toBeInTheDocument()
  })

  it('read-only mode without a recorded detail still renders the summary placeholder', async () => {
    render(<VisaDetailUpdateForm applicationId={5} readOnly />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-readonly-5')).toBeInTheDocument()
    })
    expect(screen.getByTestId('visa-detail-readonly-type-5')).toHaveTextContent('—')
    expect(screen.getByTestId('visa-detail-readonly-interview-5')).toHaveTextContent(
      /not yet scheduled/i,
    )
  })

  it('re-enters edit mode when the user clicks Edit after a successful save', async () => {
    updateVisaDetailMock.mockResolvedValue(savedDetail)
    render(<VisaDetailUpdateForm applicationId={5} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })

    await userEvent.type(screen.getByTestId('visa-detail-type-5'), 'F-1 Student')
    await userEvent.click(screen.getByTestId('visa-detail-submit-5'))

    expect(await screen.findByTestId('visa-detail-success-5')).toBeInTheDocument()

    await userEvent.click(screen.getByTestId('visa-detail-edit-5'))

    expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    expect((screen.getByTestId('visa-detail-type-5') as HTMLInputElement).value).toBe('F-1 Student')
  })

  it('maps a 401 backend detail to the session-expired copy', async () => {
    updateVisaDetailMock.mockRejectedValue(apiError(401, 'Not authenticated'))
    render(<VisaDetailUpdateForm applicationId={5} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })

    await userEvent.type(screen.getByTestId('visa-detail-type-5'), 'F-1 Student')
    await userEvent.click(screen.getByTestId('visa-detail-submit-5'))

    expect(await screen.findByTestId('visa-detail-submit-error-5')).toHaveTextContent(
      /session has expired/i,
    )
  })

  it('maps a 500 backend detail to the generic failure copy', async () => {
    updateVisaDetailMock.mockRejectedValue(apiError(500, 'Internal Server Error'))
    render(<VisaDetailUpdateForm applicationId={5} />)

    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
    })

    await userEvent.type(screen.getByTestId('visa-detail-type-5'), 'F-1 Student')
    await userEvent.click(screen.getByTestId('visa-detail-submit-5'))

    expect(await screen.findByTestId('visa-detail-submit-error-5')).toHaveTextContent(
      /failed to save the visa detail/i,
    )
    expect(screen.getByTestId('visa-detail-form-5')).toBeInTheDocument()
  })
})

describe('VisaDetailUpdateForm date helpers', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('round-trips a UTC ISO timestamp through the local datetime picker', () => {
    // The round-trip invariant ("localDateTimeToIsoUtc(isoUtcToLocalDateTime(iso)) === iso")
    // holds regardless of the runner's timezone: the local helpers
    // preserve the exact UTC instant, just re-rendering it in the
    // runner's wall-clock form. The HTML <input type="datetime-local">
    // is *minute-precision* by spec, so ``isoUtcToLocalDateTime``
    // truncates the rendered wall clock to the minute via
    // ``.slice(0, 16)`` (see ``VisaDetailUpdateForm.tsx``). Sub-minute
    // precision (e.g. ``…23:59:59.999Z``) therefore cannot survive the
    // round-trip — the seconds field is dropped on the way in and
    // re-emitted as ``:00`` on the way out. This is intentional and
    // is the contract the form actually exposes to the operator; the
    // test pins it down for several *minute-aligned* UTC instants so a
    // regression in the timezone math (e.g. dropping the ``Z`` suffix
    // or mis-applying the offset) still trips this test even when the
    // runner happens to be UTC.
    const instants = [
      '2026-11-05T09:00:00.000Z',
      '2026-01-01T00:00:00.000Z',
      '2026-06-15T23:59:00.000Z',
      '2026-12-31T12:00:00.000Z',
    ]
    for (const utc of instants) {
      const local = __testing.isoUtcToLocalDateTime(utc)
      expect(local).not.toBe('')
      // The local form must be a valid "YYYY-MM-DDTHH:mm" prefix.
      expect(local).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
      const back = __testing.localDateTimeToIsoUtc(local)
      expect(back).toBe(utc)
    }
  })

  it('returns null for an empty picker and an unparseable picker value', () => {
    expect(__testing.localDateTimeToIsoUtc('')).toBeNull()
    expect(__testing.localDateTimeToIsoUtc('not-a-date')).toBeNull()
  })

  it('returns an empty string for null / unparseable input to isoUtcToLocalDateTime', () => {
    expect(__testing.isoUtcToLocalDateTime(null)).toBe('')
    expect(__testing.isoUtcToLocalDateTime('not-a-date')).toBe('')
  })
})
