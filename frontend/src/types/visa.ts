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
  created_at: string
  updated_at: string
}

/** Body for ``PUT /visa/applications/{id}/details`` (E34; Journey J27; #194). */
export interface UpdateVisaDetailRequest {
  visa_type: string
  /** ISO 8601 UTC timestamp of the embassy interview, or ``null`` if not yet scheduled. */
  interview_date: string | null
}
