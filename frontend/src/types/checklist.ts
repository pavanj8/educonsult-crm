/** Checklist types aligned with backend E26 schemas (Journey J19).

The backend ``GET /applications/{application_id}/checklist`` endpoint
(E26; sibling issue #172) returns the merged view of a stage/program
:class:`ChecklistItemTemplate` plus the latest :class:`StudentDocument`
upload against each template, with a flat shape the frontend can
render directly without further joins. These types mirror that
response exactly; keep field names in sync with
``backend/app/schemas/checklist.py`` (Requirements §5; ADR-0012).
*/

import type { PipelineStage } from './application'

/** Verification status of a student document upload (Journey J20; J22; J23). */
export type DocumentUploadStatus = 'pending' | 'approved' | 'rejected'

export const DOCUMENT_UPLOAD_STATUS_LABELS: Record<DocumentUploadStatus, string> = {
  pending: 'Pending review',
  approved: 'Approved',
  rejected: 'Rejected',
}

/**
 * One row in the merged E26 checklist response (Journey J19).
 *
 * Combines the template definition (``templateId``, ``stage``, ``name``,
 * ``description``, ``required``, ``orderIndex``) with the latest upload
 * against that template (``upload``). When no upload has been recorded
 * for the template yet, ``upload`` is ``null``.
 */
export interface ChecklistItem {
  templateId: number
  stage: PipelineStage
  name: string
  description: string | null
  required: boolean
  orderIndex: number | null
  upload: ChecklistUpload | null
}

/** Summary of the most recent upload against a checklist item. */
export interface ChecklistUpload {
  id: number
  status: DocumentUploadStatus
  originalFilename: string
  uploadedAt: string
  verifiedAt: string | null
  rejectionReason: string | null
}

/**
 * Top-level body of ``GET /applications/{application_id}/checklist``.
 *
 * ``applicationId`` echoes the path parameter so the frontend can
 * re-validate without an extra round-trip. ``items`` is sorted by
 * ``(orderIndex NULLS LAST, templateId)`` for deterministic ordering
 * (ADR-0012: stable list ordering at the API boundary).
 */
export interface ChecklistResponse {
  applicationId: number
  items: ChecklistItem[]
}