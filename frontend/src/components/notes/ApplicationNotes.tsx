import NotesThread from './NotesThread'

interface ApplicationNotesProps {
  applicationId: number
  /** The application's student id (used as the note anchor). */
  studentId: number | null
  /** Signed-in user id -- passed through to the thread for author-only controls. */
  currentUserId: number | null
  /**
   * When ``true`` the add-note form is hidden (read-only mode). Used
   * when the signed-in user lacks the ``note:create`` permission --
   * the existing notes list is still shown, but no "Add note" button
   * appears. Defaults to ``false``.
   */
  readOnly?: boolean
}

/**
 * Per-application notes widget bundled for the counselor queue and any
 * future application-detail page (E24; Journey J17; frontend ticket
 * #166). Composes the thread behind a stable testid so each row of the
 * counselor dashboard carries one tidy surface rather than three
 * siblings.
 */
export default function ApplicationNotes({
  applicationId,
  studentId,
  currentUserId,
  readOnly = false,
}: ApplicationNotesProps) {
  return (
    <section
      aria-labelledby={`application-notes-heading-${applicationId}`}
      className="application-notes"
      data-testid={`application-notes-${applicationId}`}
    >
      <h3 id={`application-notes-heading-${applicationId}`}>Internal notes</h3>
      <NotesThread
        applicationId={applicationId}
        studentId={studentId}
        currentUserId={currentUserId}
        readOnly={readOnly}
      />
    </section>
  )
}
