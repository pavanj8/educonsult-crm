import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../../api/client'
import { useDeleteNote, useUpdateNote } from '../../hooks/useNotes'
import type { Note } from '../../types/note'

interface NoteItemProps {
  note: Note
  /** Signed-in user id -- only the author may edit or delete a note. */
  currentUserId: number | null
}

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

function describeEditError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to edit this note"
    if (err.status === 404) return 'This note is no longer available'
    if (err.status === 422) return err.message || 'Invalid note content'
  }
  return 'Failed to update the note'
}

function describeDeleteError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to delete this note"
    if (err.status === 404) return 'This note is no longer available'
  }
  return 'Failed to delete the note'
}

/**
 * Single-note row in the notes-thread UI (E24; Journey J17; frontend
 * ticket #166). Renders the body, timestamp, and -- for the note's
 * author -- Edit / Delete controls that swap the body in place.
 *
 * The component never reaches into the auth store itself; the host
 * passes the signed-in user id and we branch on equality. This keeps
 * the row presentational and trivial to test.
 */
export default function NoteItem({ note, currentUserId }: NoteItemProps) {
  const isAuthor = currentUserId !== null && note.author_user_id === currentUserId
  const [editing, setEditing] = useState(false)
  const [draftBody, setDraftBody] = useState(note.body)
  const [editError, setEditError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const { updating, update } = useUpdateNote()
  const { deleting, remove } = useDeleteNote()
  const textareaId = useId()
  const editErrorId = useId()
  const deleteErrorId = useId()

  function startEdit() {
    setDraftBody(note.body)
    setEditError(null)
    setEditing(true)
  }

  function cancelEdit() {
    setDraftBody(note.body)
    setEditError(null)
    setEditing(false)
  }

  async function handleSaveEdit(event: FormEvent) {
    event.preventDefault()
    setEditError(null)
    const trimmed = draftBody.trim()
    if (!trimmed) {
      setEditError('Note cannot be empty.')
      return
    }
    if (trimmed === note.body) {
      setEditing(false)
      return
    }
    const { note: updated, errorMessage } = await update(note.id, { body: trimmed })
    if (updated) {
      setEditing(false)
    } else if (errorMessage) {
      setEditError(errorMessage)
    }
  }

  async function handleDelete() {
    setDeleteError(null)
    const { ok, errorMessage } = await remove(note.id)
    if (!ok && errorMessage) {
      setDeleteError(errorMessage)
    }
  }

  return (
    <li
      className="note-item"
      data-testid={`note-row-${note.id}`}
      data-note-id={note.id}
    >
      <div className="note-item__meta" data-testid={`note-meta-${note.id}`}>
        <span>Staff #{note.author_user_id}</span>
        {' · '}
        <time dateTime={note.created_at}>{formatDateTime(note.created_at)}</time>
        {note.updated_at !== note.created_at ? (
          <span className="note-item__edited"> (edited)</span>
        ) : null}
      </div>
      {editing ? (
        <form
          onSubmit={handleSaveEdit}
          data-testid={`note-edit-form-${note.id}`}
          aria-label="Edit internal note"
        >
          <label htmlFor={textareaId}>Note</label>
          <textarea
            id={textareaId}
            rows={3}
            data-testid={`note-edit-body-${note.id}`}
            value={draftBody}
            onChange={(event) => setDraftBody(event.target.value)}
            disabled={updating}
            required
          />
          {editError ? (
            <p
              id={editErrorId}
              role="alert"
              data-testid={`note-edit-error-${note.id}`}
            >
              {editError || describeEditError(editError)}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={updating}
            data-testid={`note-edit-save-${note.id}`}
          >
            {updating ? 'Saving…' : 'Save'}
          </button>
          <button
            type="button"
            disabled={updating}
            onClick={cancelEdit}
            data-testid={`note-edit-cancel-${note.id}`}
          >
            Cancel
          </button>
        </form>
      ) : (
        <p
          className="note-item__body"
          data-testid={`note-body-${note.id}`}
        >
          {note.body}
        </p>
      )}
      {isAuthor && !editing ? (
        <div className="note-item__actions" data-testid={`note-actions-${note.id}`}>
          <button
            type="button"
            onClick={startEdit}
            data-testid={`note-edit-button-${note.id}`}
            disabled={deleting}
          >
            Edit
          </button>
          <button
            type="button"
            onClick={handleDelete}
            data-testid={`note-delete-button-${note.id}`}
            disabled={deleting}
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
          {deleteError ? (
            <p
              id={deleteErrorId}
              role="alert"
              data-testid={`note-delete-error-${note.id}`}
            >
              {deleteError || describeDeleteError(deleteError)}
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  )
}
