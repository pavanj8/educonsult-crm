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
  created_at: string
  updated_at: string
}

/** Path parameters for {@link uploadStudentDocument}. */
export interface UploadStudentDocumentParams {
  applicationId: number
  file: File
  /** Optional FK to the ChecklistItemTemplate this upload fulfils. */
  checklistItemTemplateId?: number | null
}

/**
 * Convert a {@link StudentDocumentUploadResponse} (the backend's full row)
 * into the {@link ChecklistUpload} shape that the checklist view renders.
 *
 * The full row carries columns the read API does not (e.g. ``storage_path``,
 * ``uploaded_by_user_id``); the checklist view only needs the
 * student-visible fields, so we project here once.
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
  }
}

/**
 * Upload a document for an application's checklist item (E27; Journey J20).
 *
 * The backend expects ``multipart/form-data`` with two parts:
 *
 * * ``file`` — the document bytes (required)
 * * ``checklist_item_template_id`` — optional FK to a
 *   :class:`ChecklistItemTemplate`. Omitted for ad-hoc uploads (the
 *   column is nullable).
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
}: UploadStudentDocumentParams): Promise<StudentDocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (checklistItemTemplateId != null) {
    formData.append('checklist_item_template_id', String(checklistItemTemplateId))
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
