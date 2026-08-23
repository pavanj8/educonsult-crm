/** Note types aligned with backend E24 schemas (Journey J17; #164, #165, #166).

The Note DB model and migration (#164), the CRUD API (#165), and this
notes-thread UI (#166) share the same shape. ``Note`` mirrors the ORM
columns -- ``application_id`` is nullable because the spec describes
notes as "per student", with the application anchor optional.

``author_user_id`` is the staff member who wrote the note
(counselor / verifier / branch manager / owner / super admin per
Requirements §5). It is opaque to the UI -- we render a generic
"Staff" label rather than a name -- because the staff directory lookup
is out of scope for this ticket and the spec does not require author
identities to be shown.

Server-side permission / branch-scope checks remain authoritative; the
UI maps 401 / 403 / 404 / 422 to readable errors.
*/

export interface Note {
  id: number
  tenant_id: number
  /** The student the note is about. */
  student_id: number
  /** Optional application anchor (matches ``applications.id``). */
  application_id: number | null
  /** Staff user id that authored the note. */
  author_user_id: number
  /** Free-text body of the note (Requirements §5 internal note content). */
  body: string
  created_at: string
  updated_at: string
}

/** Body for ``POST /notes`` (E24; Journey J17; #165 + #166).

The notes-thread UI on the application detail view always anchors new
notes to the current ``application_id``; ``student_id`` is read from the
parent application row so the caller does not have to re-supply it. */
export interface NoteCreateRequest {
  student_id: number
  application_id: number | null
  body: string
}

/** Body for ``PATCH /notes/{id}`` (E24; Journey J17; #165 + #166). */
export interface NoteUpdateRequest {
  body: string
}
