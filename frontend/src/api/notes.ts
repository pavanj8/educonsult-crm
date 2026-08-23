import { apiFetch } from './client'
import type { Note, NoteCreateRequest, NoteUpdateRequest } from '../types/note'

/**
 * Notes client for the staff-only internal counseling notes thread UI
 * (E24; Journey J17; frontend ticket #166). Mirrors the #165 backend
 * endpoints:
 *
 *   * ``POST   /notes``              - create a new internal note
 *   * ``GET    /notes``              - list notes (optionally filtered
 *                                      by ``student_id`` and/or
 *                                      ``application_id``)
 *   * ``GET    /notes/{id}``         - fetch a single note
 *   * ``PATCH  /notes/{id}``         - update an existing note (author only)
 *   * ``DELETE /notes/{id}``         - delete a note (author only)
 *
 * The router layer on the backend enforces staff-only visibility
 * (the student role is denied via the ``NOTE_READ`` / ``NOTE_CREATE``
 * permission grants). The UI hides the thread entirely on routes
 * the staff user cannot reach; this client surfaces 403 as a
 * permission error so the thread renders a friendly message rather
 * than a stack trace.
 */

export interface ListNotesParams {
  student_id?: number
  application_id?: number
}

export async function listNotes(params: ListNotesParams = {}): Promise<Note[]> {
  const search = new URLSearchParams()
  if (params.student_id !== undefined) {
    search.set('student_id', String(params.student_id))
  }
  if (params.application_id !== undefined) {
    search.set('application_id', String(params.application_id))
  }
  const query = search.toString()
  return apiFetch<Note[]>(`/notes${query ? `?${query}` : ''}`)
}

export async function getNote(noteId: number): Promise<Note> {
  return apiFetch<Note>(`/notes/${noteId}`)
}

export async function createNote(payload: NoteCreateRequest): Promise<Note> {
  return apiFetch<Note>(`/notes`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateNote(
  noteId: number,
  payload: NoteUpdateRequest,
): Promise<Note> {
  return apiFetch<Note>(`/notes/${noteId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteNote(noteId: number): Promise<void> {
  await apiFetch<void>(`/notes/${noteId}`, { method: 'DELETE' })
}
