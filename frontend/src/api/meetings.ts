import { apiFetch } from './client'
import type {
  Meeting,
  ScheduleMeetingRequest,
  UpdateMeetingRequest,
} from '../types/meeting'

/**
 * Meetings client. Mirrors the backend endpoints:
 *
 *   * ``POST /applications/{id}/meetings``  - schedule a new meeting (E22; J15)
 *   * ``GET  /applications/{id}/meetings``  - list meetings for an application (E22; J15)
 *   * ``PATCH /meetings/{id}``             - update an existing meeting (E22; J15)
 *   * ``GET  /me/meetings``                 - list meetings for the authenticated
 *                                            student (E23; J16; ticket #162).
 *                                            The backend scopes the result to
 *                                            the authenticated student's
 *                                            ``student_id``; the widget itself
 *                                            filters to upcoming (``scheduled_at
 *                                            >= now``) client-side.
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

/**
 * List the meetings that belong to the authenticated student (E23;
 * Journey J16; frontend ticket #162). The backend is expected to scope
 * the result to the caller's ``student_id``; this client does not
 * accept an application id because the student dashboard surfaces
 * meetings across all of the student's applications.
 */
export async function listMyMeetings(): Promise<Meeting[]> {
  return apiFetch<Meeting[]>(`/me/meetings`)
}
