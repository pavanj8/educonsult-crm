/** Checklist types aligned with backend E15/E26 schemas (Journey J8/J19).

The backend ``GET /applications/{application_id}/checklist`` endpoint
(E26; sibling issue #172) returns the merged view of a stage/program
:class:`ChecklistItemTemplate` plus the latest :class:`StudentDocument`
upload against each template, with a flat shape the frontend can
render directly without further joins. These types mirror that
response exactly; keep field names in sync with
``backend/app/schemas/checklist.py`` (Requirements §5; ADR-0012).

E15 (Document Checklist Template Management) adds the
:class:`ChecklistItemTemplate` CRUD endpoints mounted under
``/checklist-templates``; the request/response shapes for those
endpoints are mirrored below so the template builder UI can manage the
definitions the J19 read endpoint serves.
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

/* ------------------------------------------------------------------ *
 * E15 — Checklist template CRUD types (Journey J8; sibling #132/#134).
 *
 * The backend CRUD endpoints are mounted under
 * ``/checklist-templates`` (with ``/{id}`` for the single-resource
 * routes). The ``program_id`` field is nullable: ``null`` means
 * "applies to every program" (the common case for documents like
 * "passport" or "transcripts"). ``order_index`` is also nullable; the
 * backend uses NULL to mean "append at the end".
 * ------------------------------------------------------------------ */

/**
 * Full :class:`ChecklistItemTemplate` row as returned by the E15 admin
 * CRUD endpoints (Journey J8). The shape mirrors the backend
 * ``ChecklistItemTemplateResponse`` schema and the ORM model in
 * :mod:`backend.app.models.checklist_item_template`.
 */
export interface ChecklistItemTemplate {
  id: number
  tenant_id: number
  stage: PipelineStage
  /** ``null`` means the template applies to every program in the tenant. */
  program_id: number | null
  name: string
  description: string | null
  required: boolean
  /** ``null`` means "append at the end"; the API sorts NULLs last. */
  order_index: number | null
}

/** Payload for ``POST /checklist-templates`` (J8). */
export interface ChecklistItemTemplateCreateRequest {
  stage: PipelineStage
  /** Omit or ``null`` to apply the template to every program. */
  program_id?: number | null
  name: string
  description?: string | null
  required?: boolean
  /** Omit or ``null`` to append at the end of the stage's checklist. */
  order_index?: number | null
}

/** Payload for ``PATCH /checklist-templates/{id}`` (J8). */
export interface ChecklistItemTemplateUpdateRequest {
  stage?: PipelineStage
  program_id?: number | null
  name?: string
  description?: string | null
  required?: boolean
  order_index?: number | null
}
