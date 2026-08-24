import { useEffect, useId, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../../api/client'
import { fetchVisaDetail, updateVisaDetail } from '../../api/visa'
import type { VisaDetail } from '../../types/visa'

export interface VisaDetailUpdateFormProps {
  applicationId: number
  /** Called after a successful save so the host can refresh/close. */
  onSaved?: (applicationId: number, detail: VisaDetail) => void
  /**
   * When ``true`` the form renders as read-only: no inputs are
   * enabled, no Save button is shown. Used when the signed-in user
   * lacks ``visa:manage`` permission (e.g. counselor, document
   * verifier, receptionist, branch manager, student). Defaults to
   * ``false``.
   */
  readOnly?: boolean
}

interface VisaDetailFormState {
  visa_type: string
  /** YYYY-MM-DDTHH:mm -- ``<input type="datetime-local">`` value (local wall clock). */
  interview_date: string
}

const EMPTY_STATE: VisaDetailFormState = {
  visa_type: '',
  interview_date: '',
}

const MAX_VISA_TYPE = 100

function mapError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to update this application's visa detail"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) {
      return err.message || 'The visa detail could not be saved (check the visa type and interview date)'
    }
  }
  return 'Failed to save the visa detail'
}

/**
 * Local-date/datetime serializer for ``<input type="datetime-local">``.
 * The browser stores the value as the user's *local* wall clock
 * ("YYYY-MM-DDTHH:mm") without a timezone. The backend's
 * ``interview_date`` column is ``DateTime(timezone=True)`` (per the
 * VisaDetail model landed in ticket #193) so the API expects an ISO
 * 8601 UTC timestamp; we therefore interpret the picked value as the
 * user's local time and convert to UTC ISO 8601 with an explicit ``Z``
 * suffix so the browser's local-timezone offset is honoured (a visa
 * processor in IST picking 09:00 sees a 03:30Z interview, not a
 * 09:00Z one). Returns ``null`` for an empty picker so the backend
 * can clear a previously-recorded date — J27 explicitly treats the
 * interview date as an optional follow-up field to the visa type.
 */
function localDateTimeToIsoUtc(localValue: string): string | null {
  if (!localValue) return null
  const parsed = new Date(localValue)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toISOString()
}

/**
 * Inverse of :func:`localDateTimeToIsoUtc`: render a backend ISO 8601
 * UTC timestamp in the user's *local* "YYYY-MM-DDTHH:mm" form so it
 * can pre-fill ``<input type="datetime-local">``. Returns ``''`` for
 * ``null`` / unparseable input so the picker renders empty.
 */
function isoUtcToLocalDateTime(iso: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  // ``toISOString`` then strip the trailing "Z" and seconds -> "YYYY-MM-DDTHH:mm".
  // We round-trip through UTC ISO so the picker shows the wall clock that
  // corresponds to the backend's UTC instant in the user's timezone.
  const tzOffsetMs = date.getTimezoneOffset() * 60_000
  const local = new Date(date.getTime() - tzOffsetMs)
  return local.toISOString().slice(0, 16)
}

/**
 * Test-only surface for the form's date helpers. Exported as a
 * single object so the module keeps only the component in its
 * default export (mirrors the convention used by
 * :mod:`components/meetings/ScheduleMeetingAction`).
 */
const __testing = { localDateTimeToIsoUtc, isoUtcToLocalDateTime }

/**
 * Visa detail update form (E34; Journey J27; frontend ticket #194).
 *
 * Lets a Visa Processor (or any role with ``visa:manage``) record the
 * visa type and embassy interview date for an application at the
 * visa processing stage. The form pre-fills from ``GET
 * /visa/applications/{id}/details`` so the operator can edit an
 * existing entry in place rather than re-enter the visa type every
 * time the interview date moves. On submit the form PUTs
 * ``{ visa_type, interview_date }`` back to the same endpoint.
 *
 * The component is self-contained: the host page supplies the
 * ``onSaved`` callback but does not have to know about the visa API
 * or the timezone math.
 *
 * The component is also intentionally tolerant of the "no detail yet"
 * case: ``fetchVisaDetail`` returns ``null`` when the backend
 * responds 404, and the form starts blank (the visa type is the only
 * field the processor MUST record; the interview date can be added
 * later — J27 describes them as two fields filled in over time).
 */
export default function VisaDetailUpdateForm({
  applicationId,
  onSaved,
  readOnly = false,
}: VisaDetailUpdateFormProps) {
  const [form, setForm] = useState<VisaDetailFormState>(EMPTY_STATE)
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [savedDetail, setSavedDetail] = useState<VisaDetail | null>(null)
  const visaTypeId = useId()
  const interviewDateId = useId()
  const submitErrorId = useId()
  const loadErrorId = useId()

  // Load the current detail once per application id. A 404 is
  // collapsed into an empty form (the visa processor hasn't recorded
  // anything yet); every other error surfaces in the load error
  // banner so the operator can retry.
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(null)
    setDone(false)
    setSavedDetail(null)
    setSubmitError(null)
    setForm(EMPTY_STATE)
    fetchVisaDetail(applicationId)
      .then((detail) => {
        if (cancelled) return
        if (detail === null) {
          setForm(EMPTY_STATE)
        } else {
          setForm({
            visa_type: detail.visa_type,
            interview_date: isoUtcToLocalDateTime(detail.interview_date),
          })
          setSavedDetail(detail)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setLoadError(mapError(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [applicationId])

  const remaining = MAX_VISA_TYPE - form.visa_type.length

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)

    const trimmedType = form.visa_type.trim()
    if (!trimmedType) {
      setSubmitError('Please enter a visa type.')
      return
    }
    if (trimmedType.length > MAX_VISA_TYPE) {
      setSubmitError(`Visa type must be ${MAX_VISA_TYPE} characters or fewer.`)
      return
    }

    const interviewIso = localDateTimeToIsoUtc(form.interview_date)
    // localDateTimeToIsoUtc returns null on either empty OR
    // unparseable input — distinguish "user cleared the field"
    // (empty string, treat as null/clear) from "user typed garbage"
    // (non-empty but unparseable, treat as a validation error).
    if (form.interview_date && interviewIso === null) {
      setSubmitError('Please pick a valid date and time for the embassy interview.')
      return
    }

    setSubmitting(true)
    try {
      const saved = await updateVisaDetail(applicationId, {
        visa_type: trimmedType,
        interview_date: interviewIso,
      })
      setSavedDetail(saved)
      setDone(true)
      onSaved?.(applicationId, saved)
    } catch (err) {
      setSubmitError(mapError(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <p data-testid={`visa-detail-loading-${applicationId}`} role="status" aria-live="polite">
        Loading visa detail…
      </p>
    )
  }

  if (loadError) {
    return (
      <div data-testid={`visa-detail-load-error-${applicationId}`}>
        <p id={loadErrorId} role="alert">
          {loadError}
        </p>
      </div>
    )
  }

  if (done && savedDetail) {
    const when = savedDetail.interview_date ? new Date(savedDetail.interview_date) : null
    const whenText = when && !Number.isNaN(when.getTime())
      ? when.toLocaleString()
      : 'not yet scheduled'
    return (
      <div data-testid={`visa-detail-success-${applicationId}`} role="status" aria-live="polite">
        <p>
          Visa detail saved — type: {savedDetail.visa_type}; interview: {whenText}.
        </p>
        {!readOnly ? (
          <button
            type="button"
            data-testid={`visa-detail-edit-${applicationId}`}
            onClick={() => {
              setDone(false)
              setSubmitError(null)
            }}
          >
            Edit
          </button>
        ) : null}
      </div>
    )
  }

  if (readOnly) {
    return (
      <div data-testid={`visa-detail-readonly-${applicationId}`}>
        <p>
          Visa type: <span data-testid={`visa-detail-readonly-type-${applicationId}`}>{form.visa_type || '—'}</span>
        </p>
        <p>
          Embassy interview date:{' '}
          <span data-testid={`visa-detail-readonly-interview-${applicationId}`}>
            {form.interview_date
              ? new Date(form.interview_date).toLocaleString()
              : 'not yet scheduled'}
          </span>
        </p>
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid={`visa-detail-form-${applicationId}`}
      aria-label="Update visa detail"
    >
      <div>
        <label htmlFor={visaTypeId}>
          Visa type <span aria-hidden="true">*</span>
        </label>
        <input
          id={visaTypeId}
          type="text"
          value={form.visa_type}
          onChange={(event) => setForm((prev) => ({ ...prev, visa_type: event.target.value }))}
          maxLength={MAX_VISA_TYPE}
          required
          aria-required="true"
          disabled={submitting}
          data-testid={`visa-detail-type-${applicationId}`}
        />
        <p data-testid={`visa-detail-type-counter-${applicationId}`}>{remaining} characters remaining</p>
      </div>
      <div>
        <label htmlFor={interviewDateId}>Embassy interview date (optional)</label>
        <input
          id={interviewDateId}
          type="datetime-local"
          value={form.interview_date}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, interview_date: event.target.value }))
          }
          disabled={submitting}
          data-testid={`visa-detail-interview-${applicationId}`}
        />
      </div>
      {submitError ? (
        <p
          id={submitErrorId}
          role="alert"
          data-testid={`visa-detail-submit-error-${applicationId}`}
        >
          {submitError}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={submitting}
        data-testid={`visa-detail-submit-${applicationId}`}
      >
        {submitting ? 'Saving…' : 'Save visa detail'}
      </button>
    </form>
  )
}

export { __testing }
