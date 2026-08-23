/** Meeting types aligned with backend E22 schemas (Journey J15).

The Meeting model + migration (#159) and the schedule/list/update API
(#160) underpin this surface; the counselor-side scheduling UI (E22
frontend ticket #161) is the consumer. ``Meeting`` mirrors the ORM
columns -- ``scheduled_at`` is an ISO 8601 UTC timestamp; ``location``
and ``notes`` are optional free-text.

The fields below are what the frontend renders and submits -- nothing
extra is invented. Server-side permission / branch-scope checks remain
authoritative; the UI maps 403 / 404 / 422 to readable errors.
*/

export interface Meeting {
  id: number
  tenant_id: number
  application_id: number
  counselor_id: number
  student_id: number
  /** ISO 8601 timestamp (UTC) the meeting is scheduled for. */
  scheduled_at: string
  duration_minutes: number
  location: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

/** Body for ``POST /applications/{id}/meetings`` (E22; Journey J15; #160 + #161). */
export interface ScheduleMeetingRequest {
  /** ISO 8601 timestamp (UTC) the meeting is scheduled for. */
  scheduled_at: string
  duration_minutes: number
  location?: string | null
  notes?: string | null
}

/** Body for ``PATCH /meetings/{id}`` (E22; Journey J15; #160 + #161). */
export interface UpdateMeetingRequest {
  scheduled_at?: string
  duration_minutes?: number
  location?: string | null
  notes?: string | null
}
