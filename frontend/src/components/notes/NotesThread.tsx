import AddNoteForm from './AddNoteForm'
import NoteItem from './NoteItem'
import { useApplicationNotes } from '../../hooks/useNotes'

interface NotesThreadProps {
  applicationId: number
  /** The application's student id (used as the note's anchor). */
  studentId: number | null
  /** Signed-in user id; passed to ``NoteItem`` so it can hide Edit / Delete for non-authors. */
  currentUserId: number | null
  /**
   * When ``true`` the add-note form is hidden. The notes list is still
   * shown, so a read-only viewer (e.g. document verifier, visa
   * processor -- they have ``note:read`` but not ``note:create`` per
   * ADR-0004) can read the thread without being offered the form.
   * Defaults to ``false``.
   */
  readOnly?: boolean
  /** Called whenever a note is added/edited/deleted so the host can re-render. */
  onChanged?: () => void
}

/**
 * Notes-thread widget for the application detail view (E24; Journey
 * J17; frontend ticket #166). Loads notes anchored to the given
 * ``application_id`` and renders them in chronological order with an
 * "Add note" disclosure underneath.
 *
 * Hidden from non-staff routes via the ``readOnly`` flag -- the route
 * guard already blocks students (they are not granted
 * ``note:read``), but the ``readOnly`` switch lets a caller distinguish
 * "can read but not write" (verifier / visa processor) from "can read
 * and write" (counselor / branch manager / owner) on the same route.
 */
export default function NotesThread({
  applicationId,
  studentId,
  currentUserId,
  readOnly = false,
  onChanged,
}: NotesThreadProps) {
  const { notes, loading, error, reload } = useApplicationNotes(applicationId, studentId)

  function handleChanged() {
    void reload().then(() => onChanged?.())
  }

  if (loading) {
    return (
      <p
        role="status"
        aria-live="polite"
        data-testid={`notes-loading-${applicationId}`}
      >
        Loading notes…
      </p>
    )
  }

  if (error) {
    return (
      <p role="alert" data-testid={`notes-error-${applicationId}`}>
        {error}
      </p>
    )
  }

  return (
    <section
      className="notes-thread"
      aria-labelledby={`notes-thread-heading-${applicationId}`}
      data-testid={`notes-thread-${applicationId}`}
    >
      <h4 id={`notes-thread-heading-${applicationId}`} className="sr-only">
        Internal notes
      </h4>
      {notes.length === 0 ? (
        <p data-testid={`notes-empty-${applicationId}`}>
          No internal notes yet.
        </p>
      ) : (
        <ul className="notes-thread__list" data-testid={`notes-list-${applicationId}`}>
          {notes.map((note) => (
            <NoteItem
              key={note.id}
              note={note}
              currentUserId={currentUserId}
            />
          ))}
        </ul>
      )}
      {!readOnly && studentId !== null ? (
        <AddNoteForm
          applicationId={applicationId}
          studentId={studentId}
          onCreated={handleChanged}
        />
      ) : null}
      <button
        type="button"
        onClick={() => void reload()}
        data-testid={`notes-reload-${applicationId}`}
      >
        Refresh notes
      </button>
    </section>
  )
}
