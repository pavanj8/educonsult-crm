import { useId, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../../api/client'
import { useScheduleMeeting } from '../../hooks/useMeetings'
import type { Meeting } from '../../types/meeting'

interface ScheduleMeetingActionProps {
  applicationId: number
  /** Called after a meeting is successfully scheduled. */
  onScheduled?: (applicationId: number, meeting: Meeting) => void
  /**
   * When ``true`` the control renders as read-only: no "Schedule meeting"
   * button is shown, no form is opened. Used when the signed-in user lacks
   * ``meeting:schedule`` permission (e.g. document verifier, visa processor,
   * receptionist, student). Defaults to ``false``.
   */
  readOnly?: boolean
}

interface MeetingFormState {
  /** YYYY-MM-DDTHH:mm -- ``<input type="datetime-local">`` value. */
  when: string
  duration: number
  location: string
  notes: string
}

const DEFAULT_DURATION_MINUTES = 30

const DURATION_OPTIONS: readonly number[] = [15, 30, 45, 60, 90]

function initialFormState(): MeetingFormState {
  return {
    when: '',
    duration: DEFAULT_DURATION_MINUTES,
    location: '',
    notes: '',
  }
}

function describeError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to schedule meetings here"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) return err.message || 'Invalid meeting details'
  }
  return 'Failed to schedule the meeting'
}

/**
 * Local-date/datetime serializer for ``<input type="datetime-local">``.
 * The browser stores the value as the user's *local* wall clock ("YYYY-MM-DDTHH:mm")
 * without a timezone. The backend (ticket #160) expects an ISO 8601 UTC
 * timestamp; we therefore interpret the picked value as the user's local
 * time and convert to UTC ISO 8601 with an explicit Z suffix so the
 * browser's local-timezone offset is honoured (a counselor in IST picking
 * 09:00 sees a 03:30Z meeting, not a 09:00Z one).
 */
function localDateTimeToIsoUtc(localValue: string): string | null {
  // ``new Date('YYYY-MM-DDTHH:mm')`` is parsed as LOCAL time in modern
  // browsers -- this is what we want here, because the picker only
  // displays local wall clock.
  const local = new Date(localValue)
  if (Number.isNaN(local.getTime())) return null
  return local.toISOString()
}

function describeMeeting(meeting: Meeting): string {
  const when = new Date(meeting.scheduled_at)
  const whenText = Number.isNaN(when.getTime())
    ? meeting.scheduled_at
    : when.toLocaleString()
  const location = meeting.location ? ` — ${meeting.location}` : ''
  return `${whenText} (${meeting.duration_minutes} min)${location}`
}

/**
 * Schedule-meeting control for the counselor dashboard (E22; Journey
 * J15; frontend ticket #161). Rendered on each application row of the
 * counselor queue so a counselor (or other role with ``meeting:schedule``)
 * can pick a date/time, duration, optional location, and optional notes
 * and submit to ``POST /applications/{id}/meetings``.
 *
 * The component is self-contained: the host page supplies the
 * ``onScheduled`` callback (typically reloading that row's meeting
 * list) but does not have to know about the meeting API.
 *
 * ``describeMeeting`` and ``localDateTimeToIsoUtc`` are exported as a
 * named testing-only surface so the unit tests can exercise the formatters
 * without instantiating the component (and thus without needing
 * window.fetch mocks).
 */
export default function ScheduleMeetingAction({
  applicationId,
  onScheduled,
  readOnly = false,
}: ScheduleMeetingActionProps) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<MeetingFormState>(initialFormState)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const { submitting, schedule } = useScheduleMeeting()
  const whenId = useId()
  const durationId = useId()
  const locationId = useId()
  const notesId = useId()
  const errorId = useId()

  // Reset form when re-opening so an older attempt's values don't leak
  // across. Done state is a separate axis so the success message can
  // live until the user navigates away or explicitly closes it.
  function handleOpen() {
    setSubmitError(null)
    setForm(initialFormState())
    setDone(false)
    setOpen(true)
  }

  function handleCancel() {
    setSubmitError(null)
    setOpen(false)
  }

  const durationOptions = useMemo(() => DURATION_OPTIONS, [])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)

    const scheduledUtc = localDateTimeToIsoUtc(form.when)
    if (!scheduledUtc) {
      setSubmitError('Please pick a valid date and time for the meeting.')
      return
    }
    if (!Number.isFinite(form.duration) || form.duration < 1) {
      setSubmitError('Please pick a valid duration for the meeting.')
      return
    }

    const { meeting, errorMessage } = await schedule(applicationId, {
      scheduled_at: scheduledUtc,
      duration_minutes: form.duration,
      location: form.location.trim() ? form.location.trim() : null,
      notes: form.notes.trim() ? form.notes.trim() : null,
    })

    if (meeting) {
      setDone(true)
      onScheduled?.(applicationId, meeting)
    } else if (errorMessage) {
      setSubmitError(errorMessage)
    }
  }

  if (done) {
    return (
      <p
        role="status"
        data-testid={`schedule-meeting-success-${applicationId}`}
        aria-live="polite"
      >
        Meeting scheduled.
      </p>
    )
  }

  if (readOnly || !open) {
    return (
      <div data-testid={`schedule-meeting-summary-${applicationId}`}>
        {!readOnly ? (
          <button
            type="button"
            data-testid={`schedule-meeting-open-${applicationId}`}
            onClick={handleOpen}
          >
            Schedule meeting
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid={`schedule-meeting-form-${applicationId}`}
      aria-label="Schedule meeting"
    >
      <div>
        <label htmlFor={whenId}>Date and time</label>
        <input
          id={whenId}
          type="datetime-local"
          data-testid={`schedule-meeting-when-${applicationId}`}
          value={form.when}
          onChange={(event) => setForm((prev) => ({ ...prev, when: event.target.value }))}
          disabled={submitting}
          required
          aria-describedby={submitError ? errorId : undefined}
        />
      </div>
      <div>
        <label htmlFor={durationId}>Duration (minutes)</label>
        <select
          id={durationId}
          data-testid={`schedule-meeting-duration-${applicationId}`}
          value={form.duration}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, duration: Number(event.target.value) }))
          }
          disabled={submitting}
        >
          {durationOptions.map((option) => (
            <option key={option} value={option}>
              {option} min
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor={locationId}>Location (optional)</label>
        <input
          id={locationId}
          type="text"
          maxLength={255}
          data-testid={`schedule-meeting-location-${applicationId}`}
          value={form.location}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, location: event.target.value }))
          }
          disabled={submitting}
        />
      </div>
      <div>
        <label htmlFor={notesId}>Notes (optional)</label>
        <textarea
          id={notesId}
          rows={3}
          data-testid={`schedule-meeting-notes-${applicationId}`}
          value={form.notes}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, notes: event.target.value }))
          }
          disabled={submitting}
        />
      </div>
      {submitError ? (
        <p
          id={errorId}
          role="alert"
          data-testid={`schedule-meeting-error-${applicationId}`}
        >
          {submitError}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={submitting}
        data-testid={`schedule-meeting-submit-${applicationId}`}
      >
        {submitting ? 'Scheduling…' : 'Schedule meeting'}
      </button>
      <button
        type="button"
        onClick={handleCancel}
        disabled={submitting}
        data-testid={`schedule-meeting-cancel-${applicationId}`}
      >
        Cancel
      </button>
    </form>
  )
}

export const __testing = { describeMeeting, localDateTimeToIsoUtc, describeError }
