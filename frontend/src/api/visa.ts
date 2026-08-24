/** Visa API client (E34; Journey J27; frontend ticket #194).

Mirrors the backend endpoints the E34 sibling ticket will land:

* ``PUT /visa/applications/{id}/details`` — record or update the visa
  type and embassy interview date for an application at the visa
  processing stage. The backend endpoint is gated on ``visa:manage``
  (granted to ``VISA_PROCESSOR``, ``CONSULTANCY_OWNER``, and
  ``SUPER_ADMIN`` per :data:`app.rbac.permissions.ROLE_PERMISSIONS`).
* ``GET /visa/applications/{id}/details`` — load the current visa
  detail (server returns 404 when none has been recorded yet). The
  update form pre-fills its inputs from this endpoint so the visa
  processor can edit an existing entry rather than start from blank.

The :class:`VisaDetail` payload shape and the ``PUT`` body mirror
:class:`app.schemas.visa.VisaDetail` and the upcoming E34 request
schema on the backend (ticket #193 landed the persisted model +
migration; the API lands in the E34 backend ticket that runs in
parallel with this frontend ticket).
*/

import { apiFetch } from './client'
import type { UpdateVisaDetailRequest, VisaDetail } from '../types/visa'

/**
 * Load the visa detail recorded for an application (E34; Journey J27).
 *
 * Returns ``null`` when the backend responds with 404 — the visa
 * processor has not recorded a detail for this application yet, so
 * the form should start blank rather than treat the absence as an
 * error. Any other non-2xx response raises an :class:`ApiError` like
 * every other call through :func:`apiFetch`.
 */
export async function fetchVisaDetail(applicationId: number): Promise<VisaDetail | null> {
  try {
    return await apiFetch<VisaDetail>(`/visa/applications/${applicationId}/details`)
  } catch (err) {
    // Surface 404 as "no detail recorded yet" so the caller can decide
    // whether to render an empty form (record-new flow) or a populated
    // form (edit flow). All other errors propagate.
    if (err instanceof Error && 'status' in err && (err as { status: number }).status === 404) {
      return null
    }
    throw err
  }
}

/**
 * Record or update the visa type and embassy interview date for an
 * application (E34; Journey J27; frontend #194). Backed by
 * ``PUT /visa/applications/{id}/details``.
 *
 * The backend enforces:
 *
 * * ``visa:manage`` permission (visa processor / consultancy owner /
 *   super admin).
 * * The application must be in the caller's tenant (cross-tenant
 *   access surfaces as 404 — never 403 — to prevent enumeration).
 * * ``visa_type`` is required and must be a non-empty trimmed string
 *   within the column's 100-char ceiling.
 * * ``interview_date``, when supplied, is timezone-aware and the
 *   blank / null case clears the previously-recorded date.
 *
 * Returns the freshly-persisted :class:`VisaDetail` row so the host
 * page can re-render without an extra GET round-trip.
 */
export async function updateVisaDetail(
  applicationId: number,
  payload: UpdateVisaDetailRequest,
): Promise<VisaDetail> {
  return apiFetch<VisaDetail>(`/visa/applications/${applicationId}/details`, {
    method: 'PUT',
    body: JSON.stringify({
      visa_type: payload.visa_type.trim(),
      interview_date: payload.interview_date,
    }),
  })
}
