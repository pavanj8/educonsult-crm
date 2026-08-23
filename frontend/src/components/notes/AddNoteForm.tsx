import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import { useCreateNote } from '../../hooks/useNotes'

interface AddNoteFormProps {
  applicationId: number
  studentId: number
  /** Called after a note is successfully created. */
  onCreated?: () => void
}

/**
 * Create-note disclosure for the notes-thread UI (E24; Journey J17;
 * frontend ticket #166). The form sits below the existing thread and
 * opens behind a single "Add note" button so the rest of the row stays
 * tidy. Submits via ``POST /notes`` with the current
 * ``application_id`` / ``student_id`` anchors.
 *
 * The form is intentionally minimal -- just a body textarea -- so a
 * counselor can keep typing while a meeting is wrapping up without
 * having to fill out metadata.
 */
export default function AddNoteForm({
  applicationId,
  studentId,
  onCreated,
}: AddNoteFormProps) {
  const [open, setOpen] = useState(false)
  const [body, setBody] = useState('')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const { submitting, create } = useCreateNote()
  const textareaId = useId()
  const errorId = useId()

  function handleOpen() {
    setSubmitError(null)
    setBody('')
    setOpen(true)
  }

  function handleCancel() {
    setSubmitError(null)
    setBody('')
    setOpen(false)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)
    const trimmed = body.trim()
    if (!trimmed) {
      setSubmitError('Please write something before adding the note.')
      return
    }
    const { note, errorMessage } = await create(applicationId, studentId, {
      body: trimmed,
    })
    if (note) {
      setBody('')
      setOpen(false)
      onCreated?.()
    } else if (errorMessage) {
      setSubmitError(errorMessage)
    }
  }

  if (!open) {
    return (
      <div data-testid={`add-note-summary-${applicationId}`}>
        <button
          type="button"
          data-testid={`add-note-open-${applicationId}`}
          onClick={handleOpen}
        >
          Add note
        </button>
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid={`add-note-form-${applicationId}`}
      aria-label="Add internal note"
    >
      <div>
        <label htmlFor={textareaId}>Note</label>
        <textarea
          id={textareaId}
          rows={3}
          data-testid={`add-note-body-${applicationId}`}
          value={body}
          onChange={(event) => setBody(event.target.value)}
          disabled={submitting}
          required
          aria-describedby={submitError ? errorId : undefined}
        />
      </div>
      {submitError ? (
        <p
          id={errorId}
          role="alert"
          data-testid={`add-note-error-${applicationId}`}
        >
          {submitError}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={submitting}
        data-testid={`add-note-submit-${applicationId}`}
      >
        {submitting ? 'Adding…' : 'Add note'}
      </button>
      <button
        type="button"
        onClick={handleCancel}
        disabled={submitting}
        data-testid={`add-note-cancel-${applicationId}`}
      >
        Cancel
      </button>
    </form>
  )
}
