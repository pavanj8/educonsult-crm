import { useId, useState } from 'react'
import type { FormEvent } from 'react'

const MAX_COMMENT = 2000

interface ApproveActionProps {
  documentId: number
  documentLabel: string
  onApprove: (documentId: number, comment?: string) => Promise<void>
}

/**
 * Per-row approve action for the verifier queue (E29; Journey J22). A "Approve"
 * button reveals an accessible form with an OPTIONAL comment (approval needs no
 * mandatory note, unlike reject). On success the parent removes the row; on
 * error the form stays open with a user-readable message.
 */
export default function ApproveAction({ documentId, documentLabel, onApprove }: ApproveActionProps) {
  const [open, setOpen] = useState(false)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const commentId = useId()
  const errorId = useId()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await onApprove(documentId, comment)
      // Success: the parent removes this row from the queue, unmounting us.
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve the document')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) {
    return (
      <button type="button" data-testid={`approve-open-${documentId}`} onClick={() => setOpen(true)}>
        Approve
      </button>
    )
  }

  const remaining = MAX_COMMENT - comment.length

  return (
    <form onSubmit={handleSubmit} data-testid={`approve-form-${documentId}`} aria-label={`Approve ${documentLabel}`}>
      <label htmlFor={commentId}>Approval comment (optional)</label>
      <textarea
        id={commentId}
        value={comment}
        onChange={(event) => setComment(event.target.value)}
        maxLength={MAX_COMMENT}
        aria-describedby={error ? errorId : undefined}
        disabled={submitting}
        data-testid={`approve-comment-${documentId}`}
      />
      <p data-testid={`approve-counter-${documentId}`}>{remaining} characters remaining</p>
      {error ? (
        <p id={errorId} role="alert" data-testid={`approve-error-${documentId}`}>
          {error}
        </p>
      ) : null}
      <button type="submit" disabled={submitting} data-testid={`approve-submit-${documentId}`}>
        {submitting ? 'Approving…' : 'Confirm approval'}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        disabled={submitting}
        data-testid={`approve-cancel-${documentId}`}
      >
        Cancel
      </button>
    </form>
  )
}
