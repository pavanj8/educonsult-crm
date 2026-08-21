import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../../api/client'
import { markRejected } from '../../api/applications'

const MAX_REASON = 2000

interface MarkRejectedActionProps {
  applicationId: number
  onRejected?: (applicationId: number) => void
}

function mapError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to reject this application"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) return err.message || 'This application cannot be rejected from its current stage'
  }
  return 'Failed to reject the application'
}

/**
 * Staff "Mark Rejected" action for an application (E39; Journey J32). A button
 * reveals an accessible form with a REQUIRED reason (mirrors the backend
 * contract: 1..2000 chars, trimmed). On success the host is notified; on error
 * the form stays open with a user-readable message.
 */
export default function MarkRejectedAction({ applicationId, onRejected }: MarkRejectedActionProps) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const reasonId = useId()
  const validationId = useId()
  const submitErrorId = useId()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)
    if (!reason.trim()) {
      setValidationError('A rejection reason is required')
      return
    }
    setValidationError(null)
    setSubmitting(true)
    try {
      await markRejected(applicationId, reason.trim())
      setDone(true)
      onRejected?.(applicationId)
    } catch (err) {
      setSubmitError(mapError(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <p role="status" data-testid={`mark-rejected-success-${applicationId}`}>
        Application marked rejected.
      </p>
    )
  }

  if (!open) {
    return (
      <button type="button" data-testid={`mark-rejected-open-${applicationId}`} onClick={() => setOpen(true)}>
        Mark rejected
      </button>
    )
  }

  const describedBy =
    [validationError ? validationId : null, submitError ? submitErrorId : null].filter(Boolean).join(' ') || undefined
  const remaining = MAX_REASON - reason.length

  return (
    <form onSubmit={handleSubmit} data-testid={`mark-rejected-form-${applicationId}`} aria-label="Mark application rejected">
      <label htmlFor={reasonId}>
        Rejection reason <span aria-hidden="true">*</span>
      </label>
      <textarea
        id={reasonId}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        maxLength={MAX_REASON}
        required
        aria-required="true"
        aria-invalid={validationError ? true : undefined}
        aria-describedby={describedBy}
        disabled={submitting}
        data-testid={`mark-rejected-reason-${applicationId}`}
      />
      <p data-testid={`mark-rejected-counter-${applicationId}`}>{remaining} characters remaining</p>
      {validationError ? (
        <p id={validationId} role="alert" data-testid={`mark-rejected-validation-${applicationId}`}>
          {validationError}
        </p>
      ) : null}
      {submitError ? (
        <p id={submitErrorId} role="alert" data-testid={`mark-rejected-error-${applicationId}`}>
          {submitError}
        </p>
      ) : null}
      <button type="submit" disabled={submitting} data-testid={`mark-rejected-submit-${applicationId}`}>
        {submitting ? 'Rejecting…' : 'Confirm rejection'}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        disabled={submitting}
        data-testid={`mark-rejected-cancel-${applicationId}`}
      >
        Cancel
      </button>
    </form>
  )
}
