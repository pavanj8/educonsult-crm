import { apiFetch } from './client'
import type { Application, CreateApplicationRequest } from '../types/application'

export async function fetchApplications(): Promise<Application[]> {
  return apiFetch<Application[]>('/applications')
}

export async function createApplication(
  payload: CreateApplicationRequest,
): Promise<Application> {
  return apiFetch<Application>('/applications', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export interface StageHistoryEntry {
  id: number
  application_id: number
  from_stage: string | null
  to_stage: string
  changed_by_user_id: number | null
  changed_at: string
  reason: string | null
}

export interface StageTransitionResult {
  application: Application
  history_entry: StageHistoryEntry
}

/**
 * Mark an application ENROLLED with optional details (E38; Journey J31; #203).
 * Backed by ``POST /applications/{id}/mark-enrolled``.
 */
export async function markEnrolled(
  applicationId: number,
  details?: string,
): Promise<StageTransitionResult> {
  return apiFetch<StageTransitionResult>(`/applications/${applicationId}/mark-enrolled`, {
    method: 'POST',
    body: JSON.stringify({ details: details && details.trim() ? details.trim() : null }),
  })
}
