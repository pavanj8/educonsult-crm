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

/** Body for ``PATCH /visa/applications/{id}/outcome`` (E35; Journey J28; issue #196).

The visa outcome is a free-text string label (e.g. ``"approved"``,
``"rejected"``, ``"pending"``) rather than a hard-coded enum: the spec
does not promise an admin-managed master list of outcomes for v1
(master data in J7 covers countries / universities / programs) and the
catalogue of outcome labels may grow over time. The 32-char ceiling
matches the persisted column length on
:class:`app.models.visa_outcome.VisaOutcome`.

``outcome_date`` is the optional timestamp at which the outcome was
decided (J28). Nullable so the visa processor can save a draft outcome
without committing to a date. The body accepts either an ISO 8601
timestamp (``"2026-09-30T10:00:00Z"``) or ``null``.

``notes`` is optional free-text context the visa processor records
alongside the outcome (e.g. embassy interview comments), mirroring the
2000-char ceiling on :class:`UpdateVisaOutcomeRequest` notes.

At least one of ``status`` / ``outcome_date`` / ``notes`` MUST be
supplied: a no-op outcome update is rejected at 422. ``status`` is
required when no :class:`VisaOutcome` row exists yet for the
application. The component enforces these rules client-side before
issuing the PATCH; the backend (``updateVisaOutcomeRequest`` validator)
also enforces them, so a stale UI is caught server-side too.
*/

export interface UpdateVisaOutcomePayload {
  status?: string | null
  outcome_date?: string | null
  notes?: string | null
}

/** Persisted visa outcome row (E35; Journey J28).

Mirrors :class:`app.schemas.visa.VisaOutcomeResponse` -- the row
returned by ``PATCH /visa/applications/{id}/outcome`` (sibling backend
ticket #195). The unique constraint on ``application_id`` guarantees
there is at most one row per application, so this is the *current*
outcome (not a history).
*/

export interface VisaOutcome {
  id: number
  tenant_id: number
  application_id: number
  status: string
  outcome_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
}
