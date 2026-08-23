import { apiFetch } from './client'
import type { ChecklistUpload, DocumentUploadStatus } from '../types/checklist'

/**
 * Response body for ``POST /applications/{application_id}/documents``
 * (E27; Journey J20; sibling backend ticket #175).
 *
 * Mirrors the backend :class:`StudentDocumentUploadResponse` shape so the
 * frontend can drop the result straight into the checklist view's
 * ``upload`` slot without further client-side mapping. The uploaded
 * document starts in ``pending`` state until a Document Verifier acts
 * (Journey J22 / J23).
 */
export interface StudentDocumentUploadResponse {
  id: number
  tenant_id: number
  application_id: number
  checklist_item_template_id: number | null
  status: DocumentUploadStatus
  original_filename: string
  content_type: string
  size_bytes: number
  storage_path: string
  uploaded_by_user_id: number
  uploaded_at: string
  verified_at: string | null
  rejection_reason: string | null
  /**
   * Self-FK to the previously-rejected :class:`StudentDocument` this
   * row replaced (E31; Journey J24; sibling backend ticket #187).
   * ``null`` for every initial upload; populated on the re-upload path.
   */
  supersedes_id: number | null
  created_at: string
  updated_at: string
}

/** Path parameters for {@link uploadStudentDocument}. */
export interface UploadStudentDocumentParams {
  applicationId: number
  file: File
  /** Optional FK to the ChecklistItemTemplate this upload fulfils. */
  checklistItemTemplateId?: number | null
  /**
   * Optional id of a previously rejected :class:`StudentDocument` this
   * upload replaces (E31; Journey J24; sibling backend ticket #187).
   * When set, the backend persists the new row with
   * ``supersedes_id`` pointing at the rejected predecessor and leaves
   * the rejected row's status / rejection_reason / verifier /
   * ``verified_at`` intact (Requirements §8: audit trail).
   *
   * The backend rejects (422) attempts to supersede a non-rejected
   * predecessor or one from a different application / tenant, so the
   * frontend only ever needs to pass this when the most recent upload
   * on the checklist item is in ``rejected`` status.
   */
  supersedesDocumentId?: number | null
}

/**
 * Convert a {@link StudentDocumentUploadResponse} (the backend's full row)
 * into the {@link ChecklistUpload} shape that the checklist view renders.
 *
 * The full row carries columns the read API does not (e.g. ``storage_path``,
 * ``uploaded_by_user_id``); the checklist view only needs the
 * student-visible fields, so we project here once.
 *
 * ``supersedesDocumentId`` is propagated so the re-upload flow (E31 /
 * Journey J24) can refresh the checklist view in place after a
 * successful re-upload — the parent's reload is the canonical
 * refresh path, but having the field on the projection keeps the
 * shape future-proof if the row is later displayed directly.
 */
export function toChecklistUpload(
  response: StudentDocumentUploadResponse,
): ChecklistUpload {
  return {
    id: response.id,
    status: response.status,
    originalFilename: response.original_filename,
    uploadedAt: response.uploaded_at,
    verifiedAt: response.verified_at,
    rejectionReason: response.rejection_reason,
    supersedesDocumentId: response.supersedes_id,
  }
}

/**
 * Upload a document for an application's checklist item (E27; Journey J20;
 * E31 / Journey J24 re-upload support added in issue #188).
 *
 * The backend expects ``multipart/form-data`` with up to three parts:
 *
 * * ``file`` — the document bytes (required)
 * * ``checklist_item_template_id`` — optional FK to a
 *   :class:`ChecklistItemTemplate`. Omitted for ad-hoc uploads (the
 *   column is nullable).
 * * ``supersedes_document_id`` — optional id of a previously rejected
 *   :class:`StudentDocument` this upload replaces (E31 / Journey J24
 *   / sibling backend ticket #187). Omitted on initial uploads and on
 *   re-uploads against a non-rejected predecessor; when set, the
 *   backend persists the new row with ``supersedes_id`` pointing at
 *   the rejected predecessor and rejects (422) any attempt to
 *   supersede a non-rejected / cross-application / cross-tenant
 *   document.
 *
 * The request is sent through {@link apiFetch} with the JSON
 * ``Content-Type`` header suppressed so the browser sets the correct
 * ``multipart/form-data; boundary=...`` boundary. The auth bearer
 * token is added automatically by {@link apiFetch}.
 */
export async function uploadStudentDocument({
  applicationId,
  file,
  checklistItemTemplateId,
  supersedesDocumentId,
}: UploadStudentDocumentParams): Promise<StudentDocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (checklistItemTemplateId != null) {
    formData.append('checklist_item_template_id', String(checklistItemTemplateId))
  }
  if (supersedesDocumentId != null) {
    formData.append('supersedes_document_id', String(supersedesDocumentId))
  }

  return apiFetch<StudentDocumentUploadResponse>(
    `/applications/${applicationId}/documents`,
    {
      method: 'POST',
      body: formData,
      skipContentType: true,
    },
  )
}
