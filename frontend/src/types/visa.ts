<<<<<<< HEAD
/** Visa types aligned with backend E34 schemas (Journey J27).

The :class:`VisaDetail` shape mirrors the persisted model that ticket #193
(Backend: VisaDetail model + migration) landed on main: one row per
application with a short text visa type and an optional timezone-aware
embassy interview date. The model deliberately does NOT carry outcome
fields (those are owned by the E35 follow-up ticket, Journey J28).

``UpdateVisaDetailRequest`` is the body the visa detail update form
(frontend ticket #194) submits. ``visa_type`` is required (it is the
*visa type* being recorded) and ``interview_date`` is optional: J27
describes them as two fields the visa processor fills in over time,
not as a single atomic entry, so the form must accept recording the
visa type ahead of the interview date being known.

The ``interview_date`` field is sent as an ISO 8601 UTC timestamp to
match the backend ``DateTime(timezone=True)`` column. The form's
``<input type="datetime-local">`` value is the operator's local wall
clock; conversion to UTC happens in the form layer (mirrors the
timezone handling already used by :mod:`components/meetings`).
*/

export interface VisaDetail {
  id: number
  tenant_id: number
  application_id: number
  /** Short text label (e.g. "F-1 Student", "Tier 4 Student"). */
  visa_type: string
  /** ISO 8601 UTC timestamp of the embassy interview, or ``null`` if not yet scheduled. */
  interview_date: string | null
=======
/** Visa-stage applications queue types (E33; Journey J26; frontend #192).

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
>>>>>>> origin/main
  created_at: string
  updated_at: string
}

<<<<<<< HEAD
/** Body for ``PUT /visa/applications/{id}/details`` (E34; Journey J27; #194). */
export interface UpdateVisaDetailRequest {
  visa_type: string
  /** ISO 8601 UTC timestamp of the embassy interview, or ``null`` if not yet scheduled. */
  interview_date: string | null
=======
/** Paginated visa-stage applications queue (E33; J26). */
export interface VisaStageQueue {
  items: VisaStageQueueItem[]
  total: number
  limit: number
  offset: number
>>>>>>> origin/main
}
