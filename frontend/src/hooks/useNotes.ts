import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import {
  createNote as apiCreateNote,
  deleteNote as apiDeleteNote,
  listNotes as apiListNotes,
  updateNote as apiUpdateNote,
} from '../api/notes'
import { hasAccessToken } from '../store/authStorage'
import type { Note, NoteCreateRequest, NoteUpdateRequest } from '../types/note'

interface UseApplicationNotesResult {
  notes: Note[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
}

/**
 * Hook for the application-detail notes-thread UI (E24; Journey J17;
 * frontend ticket #166). Loads the notes anchored to a single
 * application via ``GET /notes?application_id={id}`` and exposes a
 * ``reload`` callback so the host can re-fetch after create / update /
 * delete.
 *
 * Defensive scoping:
 *  * Without an access token, returns an empty list (prevents a flash
 *    of 401 noise before the auth provider mounts).
 *  * 403 surfaces as a permission error -- the user can see the thread
 *    but cannot read its contents. This is unusual (the route guard
 *    should already block non-staff users) but is robust against a
 *    permission change since login.
 *  * 401 surfaces as a sign-in reminder.
 *  * Other network / unknown errors fall back to a generic message.
 */
export function useApplicationNotes(
  applicationId: number,
  studentId: number | null,
): UseApplicationNotesResult {
  const [notes, setNotes] = useState<Note[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!hasAccessToken() || studentId === null) {
      setNotes([])
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setNotes(await apiListNotes({ application_id: applicationId }))
    } catch (err) {
      if (isApiError(err)) {
        if (err.status === 403) {
          setError('You do not have permission to view notes for this application')
        } else if (err.status === 401) {
          setError('Sign in to view notes for this application')
        } else if (err.status === 404) {
          setError('Application not found')
        } else {
          setError('Failed to load notes for this application')
        }
      } else {
        setError('Failed to load notes for this application')
      }
    } finally {
      setLoading(false)
    }
  }, [applicationId, studentId])

  useEffect(() => {
    void load()
  }, [load])

  return { notes, loading, error, reload: load }
}

interface UseCreateNoteResult {
  submitting: boolean
  /**
   * Create a note for the given application. Resolves to either the
   * freshly-created ``Note`` (success) or ``null`` (failure). On
   * failure, ``errorMessage`` carries the user-readable description.
   */
  create: (
    applicationId: number,
    studentId: number,
    payload: { body: string },
  ) => Promise<{ note: Note | null; errorMessage: string | null }>
  submitError: string | null
}

/**
 * Hook for the create-note form on the application detail view (E24;
 * Journey J17; #166).
 *
 * ``create`` resolves to ``{ note, errorMessage }``. On success, ``note``
 * is the created object and ``errorMessage`` is ``null``. On failure,
 * ``note`` is ``null`` and ``errorMessage`` carries a user-readable
 * description.
 */
export function useCreateNote(): UseCreateNoteResult {
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const create = useCallback(
    async (
      applicationId: number,
      studentId: number,
      payload: { body: string },
      onCreated?: (note: Note) => void,
    ): Promise<{ note: Note | null; errorMessage: string | null }> => {
      setSubmitting(true)
      setSubmitError(null)
      const request: NoteCreateRequest = {
        student_id: studentId,
        application_id: applicationId,
        body: payload.body,
      }
      try {
        const note = await apiCreateNote(request)
        onCreated?.(note)
        return { note, errorMessage: null }
      } catch (err) {
        const message = describeCreateError(err)
        setSubmitError(message)
        return { note: null, errorMessage: message }
      } finally {
        setSubmitting(false)
      }
    },
    [],
  )

  return { submitting, submitError, create }
}

function describeCreateError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to add notes here"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) return err.message || 'Invalid note content'
  }
  return 'Failed to add the note'
}

interface UseUpdateNoteResult {
  updating: boolean
  update: (
    noteId: number,
    payload: NoteUpdateRequest,
  ) => Promise<{ note: Note | null; errorMessage: string | null }>
  updateError: string | null
}

/** Hook for editing the body of an existing note (author only). */
export function useUpdateNote(): UseUpdateNoteResult {
  const [updating, setUpdating] = useState(false)
  const [updateError, setUpdateError] = useState<string | null>(null)

  const update = useCallback(
    async (
      noteId: number,
      payload: NoteUpdateRequest,
      onUpdated?: (note: Note) => void,
    ): Promise<{ note: Note | null; errorMessage: string | null }> => {
      setUpdating(true)
      setUpdateError(null)
      try {
        const note = await apiUpdateNote(noteId, payload)
        onUpdated?.(note)
        return { note, errorMessage: null }
      } catch (err) {
        const message = describeUpdateError(err)
        setUpdateError(message)
        return { note: null, errorMessage: message }
      } finally {
        setUpdating(false)
      }
    },
    [],
  )

  return { updating, updateError, update }
}

function describeUpdateError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to edit this note"
    if (err.status === 404) return 'This note is no longer available'
    if (err.status === 422) return err.message || 'Invalid note content'
  }
  return 'Failed to update the note'
}

interface UseDeleteNoteResult {
  deleting: boolean
  remove: (
    noteId: number,
  ) => Promise<{ ok: boolean; errorMessage: string | null }>
  deleteError: string | null
}

/** Hook for deleting an existing note (author only). */
export function useDeleteNote(): UseDeleteNoteResult {
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const remove = useCallback(
    async (
      noteId: number,
      onDeleted?: (noteId: number) => void,
    ): Promise<{ ok: boolean; errorMessage: string | null }> => {
      setDeleting(true)
      setDeleteError(null)
      try {
        await apiDeleteNote(noteId)
        onDeleted?.(noteId)
        return { ok: true, errorMessage: null }
      } catch (err) {
        const message = describeDeleteError(err)
        setDeleteError(message)
        return { ok: false, errorMessage: message }
      } finally {
        setDeleting(false)
      }
    },
    [],
  )

  return { deleting, deleteError, remove }
}

function describeDeleteError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to delete this note"
    if (err.status === 404) return 'This note is no longer available'
  }
  return 'Failed to delete the note'
}
