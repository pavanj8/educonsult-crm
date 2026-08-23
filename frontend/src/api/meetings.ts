import { apiFetch } from './client'
import type {
  Meeting,
  ScheduleMeetingRequest,
  UpdateMeetingRequest,
} from '../types/meeting'

/**
 * Meetings client for the counselor-side scheduling UI (E22; Journey J15;
 * frontend ticket #161). Mirrors the #160 backend endpoints:
 *
 *   * ``POST /applications/{id}/meetings``  - schedule a new meeting
 *   * ``GET  /applications/{id}/meetings``  - list meetings for an application
 *   * ``PATCH /meetings/{id}``             - update an existing meeting
 *
 * These endpoints are currently being merged under ticket #160; the
 * frontend uses the published contract (model + migration in #159) so
 * the UI lands ready to call the API the moment #160 merges.
 */

export async function listMeetingsForApplication(
  applicationId: number,
): Promise<Meeting[]> {
  return apiFetch<Meeting[]>(`/applications/${applicationId}/meetings`)
}

/**
 * Schedule a new meeting for the given application. The backend
 * (ticket #160) is responsible for stamping ``counselor_id`` /
 * ``student_id`` from the authenticated user and the loaded application
 * and for tenant/branch scope enforcement; the client only submits the
 * user-visible fields (date/time, duration, optional location, optional
 * notes).
 */
export async function scheduleMeeting(
  applicationId: number,
  payload: ScheduleMeetingRequest,
): Promise<Meeting> {
  return apiFetch<Meeting>(`/applications/${applicationId}/meetings`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * Update an existing meeting. Mirrors the PATCH body the #160
 * accept-partially shape: every field is optional but at least one must
 * carry a change. The endpoint validates duration / location length
 * server-side; this client submits whatever the caller supplies.
 */
export async function updateMeeting(
  meetingId: number,
  payload: UpdateMeetingRequest,
): Promise<Meeting> {
  return apiFetch<Meeting>(`/meetings/${meetingId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}
