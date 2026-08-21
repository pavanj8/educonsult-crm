import { apiFetch } from './client'
import type { ChecklistResponse } from '../types/checklist'

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