import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../../api/client'
import { markWithdrawn } from '../../api/applications'

const MAX_REASON = 2000

interface MarkWithdrawnActionProps {
  applicationId: number
  onWithdrawn?: (applicationId: number) => void
}

function mapError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to withdraw this application"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) return err.message || 'This application cannot be withdrawn from its current stage'
  }
  return 'Failed to withdraw the application'
}

/**
 * Staff "Mark Withdrawn" action for an application (E40; Journey J33). A button
 * reveals an accessible form with a REQUIRED reason (mirrors the backend
 * contract: 1..2000 chars, trimmed). On success the host is notified; on error
 * the form stays open with a user-readable message.
 */
export default function MarkWithdrawnAction({ applicationId, onWithdrawn }: MarkWithdrawnActionProps) {
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
      setValidationError('A withdrawal reason is required')
      return
    }
    setValidationError(null)
    setSubmitting(true)
    try {
      await markWithdrawn(applicationId, reason.trim())
      setDone(true)
      onWithdrawn?.(applicationId)
    } catch (err) {
      setSubmitError(mapError(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <p role="status" data-testid={`mark-withdrawn-success-${applicationId}`}>
        Application marked withdrawn.
      </p>
    )
  }

  if (!open) {
    return (
      <button type="button" data-testid={`mark-withdrawn-open-${applicationId}`} onClick={() => setOpen(true)}>
        Mark withdrawn
      </button>
    )
  }

  const describedBy =
    [validationError ? validationId : null, submitError ? submitErrorId : null].filter(Boolean).join(' ') || undefined
  const remaining = MAX_REASON - reason.length

  return (
    <form onSubmit={handleSubmit} data-testid={`mark-withdrawn-form-${applicationId}`} aria-label="Mark application withdrawn">
      <label htmlFor={reasonId}>
        Withdrawal reason <span aria-hidden="true">*</span>
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
        data-testid={`mark-withdrawn-reason-${applicationId}`}
      />
      <p data-testid={`mark-withdrawn-counter-${applicationId}`}>{remaining} characters remaining</p>
      {validationError ? (
        <p id={validationId} role="alert" data-testid={`mark-withdrawn-validation-${applicationId}`}>
          {validationError}
        </p>
      ) : null}
      {submitError ? (
        <p id={submitErrorId} role="alert" data-testid={`mark-withdrawn-error-${applicationId}`}>
          {submitError}
        </p>
      ) : null}
      <button type="submit" disabled={submitting} data-testid={`mark-withdrawn-submit-${applicationId}`}>
        {submitting ? 'Withdrawing…' : 'Confirm withdrawal'}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        disabled={submitting}
        data-testid={`mark-withdrawn-cancel-${applicationId}`}
      >
        Cancel
      </button>
    </form>
  )
}
