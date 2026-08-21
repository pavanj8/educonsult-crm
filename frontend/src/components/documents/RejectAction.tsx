import { useId, useState } from 'react'
import type { FormEvent } from 'react'

const MAX_COMMENT = 2000

interface RejectActionProps {
  documentId: number
  documentLabel: string
  onReject: (documentId: number, comment: string) => Promise<void>
}

/**
 * Per-row reject action for the verifier queue (E30; Journey J23). A "Reject"
 * button reveals an accessible form with a REQUIRED comment (mirrors the backend
 * contract: 1..2000 chars, trimmed). On success the parent removes the row; on
 * error the form stays open with a user-readable message.
 */
export default function RejectAction({ documentId, documentLabel, onReject }: RejectActionProps) {
  const [open, setOpen] = useState(false)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const commentId = useId()
  const validationId = useId()
  const submitErrorId = useId()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)
    if (!comment.trim()) {
      setValidationError('A rejection comment is required')
      return
    }
    setValidationError(null)
    setSubmitting(true)
    try {
      await onReject(documentId, comment.trim())
      // Success: the parent removes this row from the queue, unmounting us.
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to reject the document')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) {
    return (
      <button type="button" data-testid={`reject-open-${documentId}`} onClick={() => setOpen(true)}>
        Reject
      </button>
    )
  }

  const describedBy =
    [validationError ? validationId : null, submitError ? submitErrorId : null]
      .filter(Boolean)
      .join(' ') || undefined
  const remaining = MAX_COMMENT - comment.length

  return (
    <form onSubmit={handleSubmit} data-testid={`reject-form-${documentId}`} aria-label={`Reject ${documentLabel}`}>
      <label htmlFor={commentId}>
        Rejection reason{' '}
        <span aria-hidden="true">*</span>
      </label>
      <textarea
        id={commentId}
        value={comment}
        onChange={(event) => setComment(event.target.value)}
        maxLength={MAX_COMMENT}
        required
        aria-required="true"
        aria-invalid={validationError ? true : undefined}
        aria-describedby={describedBy}
        disabled={submitting}
        data-testid={`reject-comment-${documentId}`}
      />
      <p data-testid={`reject-counter-${documentId}`}>{remaining} characters remaining</p>
      {validationError ? (
        <p id={validationId} role="alert" data-testid={`reject-validation-${documentId}`}>
          {validationError}
        </p>
      ) : null}
      {submitError ? (
        <p id={submitErrorId} role="alert" data-testid={`reject-error-${documentId}`}>
          {submitError}
        </p>
      ) : null}
      <button type="submit" disabled={submitting} data-testid={`reject-submit-${documentId}`}>
        {submitting ? 'Rejecting…' : 'Confirm rejection'}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        disabled={submitting}
        data-testid={`reject-cancel-${documentId}`}
      >
        Cancel
      </button>
    </form>
  )
}
