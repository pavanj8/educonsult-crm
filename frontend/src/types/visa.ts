/** Visa types aligned with backend E33/E34/E35 schemas (Journeys J26/J27/J28).

This file is the shared type surface for the visa stage. It collects
the queue types from E33 (visa processor dashboard, Journey J26,
frontend ticket #192), the detail / update types from E34 (visa type
& embassy interview date recording, Journey J27, frontend ticket
#194), and the outcome types from E35 (visa outcome update, Journey
J28, frontend ticket #196).

E33 — visa queue types
----------------------

The visa processor dashboard is the read-side of the visa stage: it
lists applications currently in the ``visa_processing`` pipeline
stage so the visa processor can pick the next application to work
on. The shape mirrors the E33 backend queue item payload
(:class:`app.schemas.visa.VisaStageQueueItem` from sibling ticket
#191) and the queue-pagination convention used by the E28 verifier
queue (:ts:type:`PendingDocumentQueue`).

E34 — visa detail types
-----------------------

The :ts:type:`VisaDetail` shape mirrors the persisted model that
ticket #193 (Backend: VisaDetail model + migration) landed on main:
one row per application with a short text visa type and an optional
timezone-aware embassy interview date. The model deliberately does
NOT carry outcome fields (those are owned by the E35 follow-up
ticket, Journey J28).

:ts:type:`UpdateVisaDetailRequest` is the body the visa detail update
form (frontend ticket #194) submits. ``visa_type`` is required (it is
the *visa type* being recorded) and ``interview_date`` is optional:
J27 describes them as two fields the visa processor fills in over
time, not as a single atomic entry, so the form must accept
recording the visa type ahead of the interview date being known.

The ``interview_date`` field is sent as an ISO 8601 UTC timestamp to
match the backend ``DateTime(timezone=True)`` column. The form's
``<input type="datetime-local">`` value is the operator's local wall
clock; conversion to UTC happens in the form layer (mirrors the
timezone handling already used by :mod:`components/meetings`).

E35 — visa outcome types
------------------------

:ts:type:`UpdateVisaOutcomePayload` is the body the visa outcome
update flow (frontend ticket #196) submits. ``status`` is the only
required input on first creation; ``outcome_date`` and ``notes`` are
optional context. The 32-char / 2000-char ceilings mirror the
persisted column lengths on :class:`app.models.visa_outcome.VisaOutcome`.

:ts:type:`VisaOutcome` mirrors :class:`app.schemas.visa.VisaOutcomeResponse`
-- the row returned by ``PATCH /visa/applications/{id}/outcome``
(sibling backend ticket #195). The unique constraint on
``application_id`` guarantees there is at most one row per
application.
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
