import { useCallback, useRef, useState } from 'react'

import { isApiError } from '../api/client'
import {
  toChecklistUpload,
  uploadStudentDocument,
  type StudentDocumentUploadResponse,
} from '../api/studentDocuments'
import type { ChecklistUpload } from '../types/checklist'

/**
 * Hook return shape for {@link useStudentDocumentUpload}.
 *
 * The hook intentionally exposes a single ``upload`` action rather than
 * tracking per-file state — only one upload can be in-flight per
 * checklist item at a time, and the parent {@link ChecklistView}
 * already owns the merge of ``upload`` data into the rendered item.
 */
export interface UseStudentDocumentUploadResult {
  uploading: boolean
  error: string | null
  /**
   * Upload ``file`` against the checklist item, returning the projected
   * {@link ChecklistUpload} payload on success. Throws when the upload
   * fails so the caller can decide whether to abort further UI work.
   */
  upload: (file: File) => Promise<ChecklistUpload>
  /** Clear the last error (e.g. when the user picks a new file). */
  clearError: () => void
}

/**
 * Upload a document against a checklist item (E27; Journey J20; E31
 * / Journey J24 re-upload support added in issue #188).
 *
 * Mirrors the conventions used by the other resource hooks in this
 * codebase (``useCreateApplication`` for the success-failure pattern,
 * ``useNotifications`` for action-error separation): the hook owns
 * the in-flight flag and surfaces a human-readable error message so
 * the caller can render it inline. It deliberately does **not**
 * mutate the parent checklist view's items list — the caller is
 * expected to refresh the checklist (the upload UI passes an
 * ``onUploaded`` callback that re-fetches the merged view).
 *
 * A ref-based "request token" guarantees that a slow response from a
 * stale upload can never overwrite the error state of a fresher one
 * (Requirements §8: no race-induced UI confusion around document
 * state).
 *
 * When ``supersedesDocumentId`` is supplied, the hook forwards it to
 * the backend's ``POST /applications/{application_id}/documents``
 * ``supersedes_document_id`` form field so the new row's
 * ``supersedes_id`` FK points at the rejected predecessor (E31 /
 * Journey J24 / sibling backend ticket #187). The rejected row
 * itself is never mutated by the upload endpoint.
 */
export function useStudentDocumentUpload(params: {
  applicationId: number
  checklistItemTemplateId: number | null
  /**
   * Optional id of a rejected :class:`StudentDocument` this upload
   * replaces (E31; Journey J24). Pass ``null`` (the default) for
   * initial uploads.
   */
  supersedesDocumentId?: number | null
}): UseStudentDocumentUploadResult {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const requestTokenRef = useRef(0)

  const upload = useCallback(
    async (file: File): Promise<ChecklistUpload> => {
      const token = ++requestTokenRef.current
      setUploading(true)
      setError(null)
      try {
        const response: StudentDocumentUploadResponse = await uploadStudentDocument({
          applicationId: params.applicationId,
          file,
          checklistItemTemplateId: params.checklistItemTemplateId,
          supersedesDocumentId: params.supersedesDocumentId,
        })
        if (token !== requestTokenRef.current) {
          // A newer upload has started; drop this stale success on the
          // floor so the caller's await does not race with the in-flight
          // upload. The error stays as ``null`` because the fresh
          // request owns the UI.
          throw new Error('Superseded by a newer upload')
        }
        return toChecklistUpload(response)
      } catch (err) {
        if (token !== requestTokenRef.current) {
          // The newer request owns the UI; let it surface the error.
          throw err instanceof Error ? err : new Error('Upload failed')
        }
        const message = isApiError(err)
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Failed to upload document'
        setError(message)
        throw err instanceof Error ? err : new Error(message)
      } finally {
        if (token === requestTokenRef.current) {
          setUploading(false)
        }
      }
    },
    [
      params.applicationId,
      params.checklistItemTemplateId,
      params.supersedesDocumentId,
    ],
  )

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  return { uploading, error, upload, clearError }
}
