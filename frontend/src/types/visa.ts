/** Visa types aligned with backend E33/E34 schemas (Journeys J26/J27).

This file is the shared type surface for the visa stage. It collects the
queue types from E33 (visa processor dashboard, Journey J26, frontend
ticket #192) and the detail / update types from E34 (visa type & embassy
interview date recording, Journey J27, frontend ticket #194). The two
epics build on each other: J26 lets the visa processor pick the next
application to work on, and J27 is the action that application detail
page exposes.

E34 visa detail shape
---------------------

The :ts:type:`VisaDetail` shape mirrors the persisted model that ticket
#193 (Backend: VisaDetail model + migration) landed on main: one row per
application with a short text visa type and an optional timezone-aware
embassy interview date. The model deliberately does NOT carry outcome
fields (those are owned by the E35 follow-up ticket, Journey J28).

:ts:type:`UpdateVisaDetailRequest` is the body the visa detail update
form (frontend ticket #194) submits. ``visa_type`` is required (it is
the *visa type* being recorded) and ``interview_date`` is optional: J27
describes them as two fields the visa processor fills in over time, not
as a single atomic entry, so the form must accept recording the visa
type ahead of the interview date being known.

The ``interview_date`` field is sent as an ISO 8601 UTC timestamp to
match the backend ``DateTime(timezone=True)`` column. The form's
``<input type="datetime-local">`` value is the operator's local wall
clock; conversion to UTC happens in the form layer (mirrors the
timezone handling already used by :mod:`components/meetings`).

E33 visa queue types
--------------------

The visa processor dashboard is the read-side of the visa stage: it
lists applications currently in the ``visa_processing`` pipeline
stage so the visa processor can pick the next application to work on.
The shape mirrors the E33 backend queue item payload
(:class:`app.schemas.visa.VisaStageQueueItem` from sibling ticket
#191) and the queue-pagination convention used by the E28 verifier
queue (:ts:type:`PendingDocumentQueue`).
*/

/** One row in the visa-stage applications queue (E33; J26). */
export interface VisaStageQueueItem {
  id: number
  tenant_id: number
  branch_id: number | null
  student_id: number
  assigned_counselor_id: number | null
  university_id: number
  program_id: number
  /** Always ``"visa_processing"`` for items returned by this queue. */
  stage: string
  created_at: string
  updated_at: string
}

/** Paginated visa-stage applications queue (E33; J26). */
export interface VisaStageQueue {
  items: VisaStageQueueItem[]
  total: number
  limit: number
  offset: number
}

/**
 * Persisted visa detail for one application (E34; Journey J27; #194).
 *
 * Mirrors the backend ``VisaDetail`` model landed in ticket #193. The
 * interview date is a timezone-aware UTC ISO 8601 timestamp or ``null``
 * when not yet scheduled.
 */
export interface VisaDetail {
  id: number
  tenant_id: number
  application_id: number
  /** Short text label (e.g. "F-1 Student", "Tier 4 Student"). */
  visa_type: string
  /** ISO 8601 UTC timestamp of the embassy interview, or ``null`` if not yet scheduled. */
  interview_date: string | null
  created_at: string
  updated_at: string
}

/** Body for ``PUT /visa/applications/{id}/details`` (E34; Journey J27; #194). */
export interface UpdateVisaDetailRequest {
  visa_type: string
  /** ISO 8601 UTC timestamp of the embassy interview, or ``null`` if not yet scheduled. */
  interview_date: string | null
}
