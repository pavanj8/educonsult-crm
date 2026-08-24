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

export interface AssignedApplicationsParams {
  stage?: string
}

/**
 * The signed-in staff member's assigned application queue (E21; Journey J14).
 * Backed by ``GET /applications/assigned-to-me`` (scoped server-side by role).
 */
export async function fetchAssignedApplications(
  params: AssignedApplicationsParams = {},
): Promise<Application[]> {
  const query = new URLSearchParams()
  if (params.stage) {
    query.set('stage', params.stage)
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiFetch<Application[]>(`/applications/assigned-to-me${suffix}`)
}

/**
 * Mark an application REJECTED with a REQUIRED reason (E39; Journey J32; #205).
 * Backed by ``POST /applications/{id}/mark-rejected``.
 */
export async function markRejected(
  applicationId: number,
  reason: string,
): Promise<StageTransitionResult> {
  return apiFetch<StageTransitionResult>(`/applications/${applicationId}/mark-rejected`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

/**
 * Mark an application WITHDRAWN with a REQUIRED reason (E40; Journey J33; #207).
 * Backed by ``POST /applications/{id}/mark-withdrawn``.
 */
export async function markWithdrawn(
  applicationId: number,
  reason: string,
): Promise<StageTransitionResult> {
  return apiFetch<StageTransitionResult>(`/applications/${applicationId}/mark-withdrawn`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

/**
 * Manually reassign (or unassign) the counselor on an application (E20;
 * Journey J13; frontend #154). Backed by
 * ``PATCH /applications/{id}/counselor``.
 *
 * Pass an integer ``counselorId`` to assign that counselor; pass
 * ``null`` to unassign the application's current counselor. Server-side
 * permission / branch-scope / counselor-validity checks are unchanged
 * — the backend surfaces 403 / 422 with a meaningful ``detail`` that
 * the calling UI maps to a user-readable error message.
 */
export async function reassignCounselor(
  applicationId: number,
  counselorId: number | null,
): Promise<Application> {
  return apiFetch<Application>(`/applications/${applicationId}/counselor`, {
    method: 'PATCH',
    body: JSON.stringify({ counselor_id: counselorId }),
  })
}

/**
 * Set the student's loan-tracking opt-in flag on an application (E36;
 * Journey J29; frontend #199). Backed by the future
 * ``PATCH /applications/{id}/loan-opt-in`` endpoint (the backend
 * endpoint itself is a follow-up to issue #199 and is not yet
 * implemented — see ``docs/epics.md`` E36 / E37).
 *
 * The frontend UI exposes this toggle today so the student application
 * flow has a working control surface; the call is wrapped to surface a
 * readable error when the backend endpoint is not yet wired up. Pass
 * ``true`` to opt in, ``false`` to opt out.
 */
export async function setLoanOptIn(
  applicationId: number,
  loanOptIn: boolean,
): Promise<Application> {
  return apiFetch<Application>(`/applications/${applicationId}/loan-opt-in`, {
    method: 'PATCH',
    body: JSON.stringify({ loan_opt_in: loanOptIn }),
  })
}
