import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../../api/client'
import { markEnrolled } from '../../api/applications'

const MAX_DETAILS = 2000

interface MarkEnrolledActionProps {
  applicationId: number
  /** Called after a successful enrolment so the host can refresh/close. */
  onEnrolled?: (applicationId: number) => void
}

function mapError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to mark this application enrolled"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) return err.message || 'This application cannot be marked enrolled from its current stage'
  }
  return 'Failed to mark the application enrolled'
}

/**
 * Staff "Mark Enrolled" action for an application (E38; Journey J31). A button
 * reveals an accessible form with OPTIONAL enrolment details (a positive outcome
 * needs no mandatory reason, unlike reject/withdraw). On success the host is
 * notified; on error the form stays open with a user-readable message.
 */
export default function MarkEnrolledAction({ applicationId, onEnrolled }: MarkEnrolledActionProps) {
  const [open, setOpen] = useState(false)
  const [details, setDetails] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const detailsId = useId()
  const errorId = useId()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await markEnrolled(applicationId, details)
      setDone(true)
      onEnrolled?.(applicationId)
    } catch (err) {
      setError(mapError(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <p role="status" data-testid={`mark-enrolled-success-${applicationId}`}>
        Application marked enrolled.
      </p>
    )
  }

  if (!open) {
    return (
      <button type="button" data-testid={`mark-enrolled-open-${applicationId}`} onClick={() => setOpen(true)}>
        Mark enrolled
      </button>
    )
  }

  const remaining = MAX_DETAILS - details.length

  return (
    <form onSubmit={handleSubmit} data-testid={`mark-enrolled-form-${applicationId}`} aria-label="Mark application enrolled">
      <label htmlFor={detailsId}>Enrolment details (optional)</label>
      <textarea
        id={detailsId}
        value={details}
        onChange={(event) => setDetails(event.target.value)}
        maxLength={MAX_DETAILS}
        aria-describedby={error ? errorId : undefined}
        disabled={submitting}
        data-testid={`mark-enrolled-details-${applicationId}`}
      />
      <p data-testid={`mark-enrolled-counter-${applicationId}`}>{remaining} characters remaining</p>
      {error ? (
        <p id={errorId} role="alert" data-testid={`mark-enrolled-error-${applicationId}`}>
          {error}
        </p>
      ) : null}
      <button type="submit" disabled={submitting} data-testid={`mark-enrolled-submit-${applicationId}`}>
        {submitting ? 'Marking…' : 'Confirm enrolment'}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        disabled={submitting}
        data-testid={`mark-enrolled-cancel-${applicationId}`}
      >
        Cancel
      </button>
    </form>
  )
}
