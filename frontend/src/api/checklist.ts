import { apiFetch } from './client'
import type {
  ChecklistItemTemplate,
  ChecklistItemTemplateCreateRequest,
  ChecklistItemTemplateUpdateRequest,
  ChecklistResponse,
} from '../types/checklist'

/** Path parameters for {@link fetchApplicationChecklist}. */
export interface FetchApplicationChecklistParams {
  applicationId: number
}

/**
 * Fetch the merged checklist (templates + latest upload status) for one
 * application (E26; Journey J19).
 *
 * Mirrors the backend ``GET /applications/{application_id}/checklist``
 * endpoint defined in sibling issue #172. The auth header is added
 * automatically by {@link apiFetch}.
 */
export async function fetchApplicationChecklist({
  applicationId,
}: FetchApplicationChecklistParams): Promise<ChecklistResponse> {
  return apiFetch<ChecklistResponse>(`/applications/${applicationId}/checklist`)
}

/* ------------------------------------------------------------------ *
 * E15 — Checklist template CRUD client (Journey J8; sibling #132).
 *
 * The backend exposes ``/checklist-templates`` (GET, POST) and
 * ``/checklist-templates/{id}`` (GET, PATCH, DELETE), gated by the
 * ``checklist_template:manage`` permission (granted to consultancy
 * owner + branch manager). Templates are tenant-scoped via the
 * authenticated caller's ``tenant_id`` (ADR-0004).
 * ------------------------------------------------------------------ */

/** Filter parameters for {@link fetchAdminChecklistItemTemplates}. */
export interface FetchAdminChecklistItemTemplatesParams {
  stage?: string
  program_id?: number
}

function checklistTemplatePath(id?: number): string {
  const base = '/checklist-templates'
  return typeof id === 'number' ? `${base}/${id}` : base
}

/**
 * List checklist item templates owned by the caller's tenant.
 * Optional ``stage`` / ``program_id`` query params mirror the backend
 * filter support (Journey J8; E15).
 */
export async function fetchAdminChecklistItemTemplates(
  params: FetchAdminChecklistItemTemplatesParams = {},
): Promise<ChecklistItemTemplate[]> {
  const search: string[] = []
  if (typeof params.stage === 'string' && params.stage.length > 0) {
    search.push(`stage=${encodeURIComponent(params.stage)}`)
  }
  if (typeof params.program_id === 'number' && Number.isFinite(params.program_id)) {
    search.push(`program_id=${params.program_id}`)
  }
  const query = search.length > 0 ? `?${search.join('&')}` : ''
  return apiFetch<ChecklistItemTemplate[]>(`${checklistTemplatePath()}${query}`)
}

/** Create a checklist item template (E15; Journey J8). */
export async function createAdminChecklistItemTemplate(
  payload: ChecklistItemTemplateCreateRequest,
): Promise<ChecklistItemTemplate> {
  return apiFetch<ChecklistItemTemplate>(checklistTemplatePath(), {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** Update a checklist item template (E15; Journey J8). */
export async function updateAdminChecklistItemTemplate(
  id: number,
  payload: ChecklistItemTemplateUpdateRequest,
): Promise<ChecklistItemTemplate> {
  return apiFetch<ChecklistItemTemplate>(checklistTemplatePath(id), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

/** Delete a checklist item template (E15; Journey J8). */
export async function deleteAdminChecklistItemTemplate(id: number): Promise<void> {
  await apiFetch<void>(checklistTemplatePath(id), {
    method: 'DELETE',
  })
}
