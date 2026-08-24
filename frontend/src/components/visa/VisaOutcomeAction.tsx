import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../../api/client'
import { updateVisaOutcome } from '../../api/visa'
import type { VisaOutcome } from '../../types/visa'

// Mirrors the column lengths enforced server-side by
// :class:`UpdateVisaOutcomeRequest` (32-char status, 2000-char notes),
// so the picker cannot smuggle content the backend would reject
// anyway.
const MAX_STATUS = 32
const MAX_NOTES = 2000

interface VisaOutcomeActionProps {
  applicationId: number
  /**
   * The application's existing outcome row, if the visa processor
   * has already recorded one for this application (the API enforces
   * a 1:1 unique constraint on ``application_id``). When ``null``
   * the form is in "create" mode and ``status`` becomes a required
   * input; when provided, the form prefills and every field is
   * individually optional so the visa processor can update any
   * subset. The component never derives its mode from the API —
   * the parent passes the truth.
   */
  initialOutcome?: VisaOutcome | null
  /**
   * Notified after a successful PATCH so the parent can refresh its
   * row (recompute the "outcome recorded" indicator, etc.).
   * ``outcome`` is the row as persisted by the backend.
   */
  onUpdated?: (applicationId: number, outcome: VisaOutcome) => void
}

interface OutcomeFormState {
  status: string
  /** YYYY-MM-DDTHH:mm -- ``<input type="datetime-local">`` value. */
  outcome_date: string
  notes: string
}

function initialFormState(outcome: VisaOutcome | null | undefined): OutcomeFormState {
  if (!outcome) {
    return { status: '', outcome_date: '', notes: '' }
  }
  // Convert the ISO 8601 UTC timestamp the backend stores to the
  // ``YYYY-MM-DDTHH:mm`` ``datetime-local`` format the picker wants.
  // We render the input in the user's *local* timezone so the visa
  // processor sees the date/time they expect on screen; on submit we
  // convert back to UTC ISO 8601 so the backend's timezone-aware
  // ``outcome_date`` column receives a precise instant (the backend
  // uses ``DateTime(timezone=True)`` per the E35 model docs).
  let outcome_date = ''
  if (outcome.outcome_date) {
    const date = new Date(outcome.outcome_date)
    if (!Number.isNaN(date.getTime())) {
      const pad = (n: number) => String(n).padStart(2, '0')
      outcome_date =
        `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
        `T${pad(date.getHours())}:${pad(date.getMinutes())}`
    }
  }
  return {
    status: outcome.status ?? '',
    outcome_date,
    notes: outcome.notes ?? '',
  }
}

/**
 * Convert a ``<input type="datetime-local">`` value into a UTC ISO 8601
 * string the backend accepts. Mirrors the rule used by
 * :ts:func:`localDateTimeToIsoUtc` in :ts:comp:`ScheduleMeetingAction`:
 * the browser stores the value as the user's *local* wall clock and
 * ``new Date('YYYY-MM-DDTHH:mm')`` is parsed as local time in modern
 * browsers, so the picked value is honoured as local time.
 *
 * Returns ``null`` when the value is empty / unparseable (callers can
 * then safely forward ``null`` as the outcome_date).
 */
function localDateTimeToIsoUtc(localValue: string): string | null {
  if (!localValue) return null
  const local = new Date(localValue)
  if (Number.isNaN(local.getTime())) return null
  return local.toISOString()
}

/**
 * Detect "all three fields empty after trimming". Mirrors the
 * "at least one of status / outcome_date / notes" rule on
 * :class:`UpdateVisaOutcomeRequest`. Called *before* the PATCH so the
 * visa processor gets immediate feedback; the backend enforces the same
 * rule with a 422.
 */
function hasAnyField(form: OutcomeFormState): boolean {
  return Boolean(
    form.status.trim() || form.outcome_date.trim() || form.notes.trim(),
  )
}

function hasResolvedDate(form: OutcomeFormState): boolean {
  if (!form.outcome_date.trim()) return false
  return localDateTimeToIsoUtc(form.outcome_date) !== null
}

function mapError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to update this application's outcome"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) return err.message || 'The outcome could not be updated from its current stage'
    if (err.status === 503) return 'The visa outcome service is temporarily unavailable'
  }
  return 'Failed to update the visa outcome'
}

/**
 * Per-row visa outcome update action (E35; Journey J28; frontend
 * #196). The Visa Processor dashboard's visa-queue table renders one
 * of these per application so the visa processor can record the
 * outcome (status + optional outcome date + optional notes) and
 * update it later via the same control. Mirrors the accessible
 * reveal / submit / error UX established by
 * :ts:comp:`MarkRejectedAction` and :ts:comp:`ScheduleMeetingAction`.
 *
 * Mode is driven by ``initialOutcome``: ``null`` is a fresh create
 * (status is required, the backend rejects a brand-new outcome row
 * without one); a provided outcome prefills the form and every
 * field becomes individually optional so the visa processor can
 * patch any subset (the backend merges over the existing row).
 *
 * Errors are mapped to user-readable copy but never reach the
 * backend interceptor, so the form stays open with the message and
 * the visa processor can correct and resubmit.
 */
export default function VisaOutcomeAction({
  applicationId,
  initialOutcome = null,
  onUpdated,
}: VisaOutcomeActionProps) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<OutcomeFormState>(() => initialFormState(initialOutcome))
  const [submitting, setSubmitting] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const statusId = useId()
  const dateId = useId()
  const notesId = useId()
  const validationId = useId()
  const submitErrorId = useId()

  const isCreate = initialOutcome == null
  const buttonLabel = isCreate ? 'Record outcome' : 'Update outcome'

  function handleOpen() {
    setSubmitError(null)
    setValidationError(null)
    setForm(initialFormState(initialOutcome))
    setDone(false)
    setOpen(true)
  }

  function handleCancel() {
    setSubmitError(null)
    setValidationError(null)
    setOpen(false)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)
    setValidationError(null)

    const trimmedStatus = form.status.trim()

    if (isCreate && !trimmedStatus) {
      setValidationError('An outcome status is required the first time you record an outcome')
      return
    }
    if (form.outcome_date.trim() && !hasResolvedDate(form)) {
      setValidationError('Pick a valid date and time for the outcome')
      return
    }

    // Mirror the backend's "at least one of status / outcome_date /
    // notes must be provided" validator. We check *after* the
    // create-required check above so create-mode callers don't get a
    // misleading "fill in a field" message.
    if (
      !isCreate &&
      !trimmedStatus &&
      !form.outcome_date.trim() &&
      !form.notes.trim()
    ) {
      setValidationError('Update at least one of status, outcome date, or notes')
      return
    }

    const payload = {
      status: trimmedStatus ? trimmedStatus : null,
      outcome_date: localDateTimeToIsoUtc(form.outcome_date),
      notes: form.notes.trim() ? form.notes.trim() : null,
    }

    setSubmitting(true)
    try {
      const outcome = await updateVisaOutcome(applicationId, payload)
      setDone(true)
      onUpdated?.(applicationId, outcome)
    } catch (err) {
      setSubmitError(mapError(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <p
        role="status"
        aria-live="polite"
        data-testid={`visa-outcome-success-${applicationId}`}
      >
        {isCreate ? 'Outcome recorded.' : 'Outcome updated.'}
      </p>
    )
  }

  if (!open) {
    return (
      <button
        type="button"
        data-testid={`visa-outcome-open-${applicationId}`}
        onClick={handleOpen}
      >
        {buttonLabel}
      </button>
    )
  }

  const describedBy =
    [validationError ? validationId : null, submitError ? submitErrorId : null]
      .filter(Boolean)
      .join(' ') || undefined
  const statusRemaining = MAX_STATUS - form.status.length
  const notesRemaining = MAX_NOTES - form.notes.length

  return (
    <form
      onSubmit={handleSubmit}
      data-testid={`visa-outcome-form-${applicationId}`}
      aria-label={isCreate ? 'Record visa outcome' : 'Update visa outcome'}
    >
      <div>
        <label htmlFor={statusId}>
          Outcome status{' '}
          {isCreate ? <span aria-hidden="true">*</span> : null}
        </label>
        <input
          id={statusId}
          type="text"
          value={form.status}
          maxLength={MAX_STATUS}
          required={isCreate}
          aria-required={isCreate ? 'true' : undefined}
          aria-invalid={validationError ? true : undefined}
          aria-describedby={describedBy}
          disabled={submitting}
          onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value }))}
          data-testid={`visa-outcome-status-${applicationId}`}
        />
        <p data-testid={`visa-outcome-status-counter-${applicationId}`}>
          {statusRemaining} characters remaining
        </p>
      </div>
      <div>
        <label htmlFor={dateId}>Outcome date (optional)</label>
        <input
          id={dateId}
          type="datetime-local"
          value={form.outcome_date}
          aria-describedby={describedBy}
          disabled={submitting}
          onChange={(event) => setForm((prev) => ({ ...prev, outcome_date: event.target.value }))}
          data-testid={`visa-outcome-date-${applicationId}`}
        />
      </div>
      <div>
        <label htmlFor={notesId}>Notes (optional)</label>
        <textarea
          id={notesId}
          rows={3}
          value={form.notes}
          maxLength={MAX_NOTES}
          aria-describedby={describedBy}
          disabled={submitting}
          onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
          data-testid={`visa-outcome-notes-${applicationId}`}
        />
        <p data-testid={`visa-outcome-notes-counter-${applicationId}`}>
          {notesRemaining} characters remaining
        </p>
      </div>
      {validationError ? (
        <p
          id={validationId}
          role="alert"
          data-testid={`visa-outcome-validation-${applicationId}`}
        >
          {validationError}
        </p>
      ) : null}
      {submitError ? (
        <p
          id={submitErrorId}
          role="alert"
          data-testid={`visa-outcome-error-${applicationId}`}
        >
          {submitError}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={submitting}
        data-testid={`visa-outcome-submit-${applicationId}`}
      >
        {submitting ? 'Saving…' : isCreate ? 'Record outcome' : 'Save outcome'}
      </button>
      <button
        type="button"
        onClick={handleCancel}
        disabled={submitting}
        data-testid={`visa-outcome-cancel-${applicationId}`}
      >
        Cancel
      </button>
    </form>
  )
}

export const __testing = { localDateTimeToIsoUtc, hasAnyField, hasResolvedDate }
