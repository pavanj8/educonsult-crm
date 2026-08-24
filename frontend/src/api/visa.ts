<<<<<<< HEAD
/** Visa API client (E33 read-side queue + E34 detail update).

Mirrors the backend endpoints in the visa stage area:

* ``GET /visa/applications/queue`` — paginated list of applications at
  the visa processing stage. E33; Journey J26; frontend ticket #192.
  Backed by sibling backend ticket #191.
* ``GET /visa/applications/{id}/details`` — load the current visa
  detail (server returns 404 when none has been recorded yet). E34;
  Journey J27; frontend ticket #194. The update form pre-fills its
  inputs from this endpoint so the visa processor can edit an
  existing entry rather than start from blank.
* ``PUT /visa/applications/{id}/details`` — record or update the
  visa type and embassy interview date for an application at the
  visa processing stage. E34; Journey J27; frontend ticket #194.
  Gated on ``visa:manage`` (granted to ``VISA_PROCESSOR``,
  ``CONSULTANCY_OWNER``, and ``SUPER_ADMIN`` per
  :data:`app.rbac.permissions.ROLE_PERMISSIONS`). Backed by the E34
  backend endpoint that lands in parallel with this frontend ticket;
  ticket #193 landed the persisted model + migration on the backend
  side.
*/

import { apiFetch, isApiError } from './client'
import type { UpdateVisaDetailRequest, VisaDetail, VisaStageQueue } from '../types/visa'
=======
import { apiFetch } from './client'
import type { UpdateVisaOutcomePayload, VisaOutcome, VisaStageQueue } from '../types/visa'
>>>>>>> origin/main

export interface VisaStageQueueParams {
  limit?: number
  offset?: number
}

/**
 * Fetch the authenticated visa processor's applications queue
 * (E33; Journey J26; #192). Backed by
 * ``GET /visa/applications/queue`` — the read-side of the visa
 * processor dashboard (mounted at prefix ``/visa`` in
 * ``backend/app/main.py``; see sibling backend ticket #191). The
 * server is responsible for tenant-scoping and restricting the
 * result to applications whose pipeline stage is currently
 * ``visa_processing`` (Requirements §5).
 */
export async function fetchVisaStageQueue(
  params: VisaStageQueueParams = {},
): Promise<VisaStageQueue> {
  const query = new URLSearchParams()
  if (params.limit != null) {
    query.set('limit', String(params.limit))
  }
  if (params.offset != null) {
    query.set('offset', String(params.offset))
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiFetch<VisaStageQueue>(`/visa/applications/queue${suffix}`)
}

/**
<<<<<<< HEAD
 * Load the visa detail recorded for an application (E34; Journey J27;
 * #194). Backed by ``GET /visa/applications/{id}/details``.
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
    // form (edit flow). All other errors propagate. ``isApiError`` is
    // the project's standard discriminator for ``ApiError`` instances
    // raised by :func:`apiFetch`.
    if (isApiError(err) && err.status === 404) {
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
 * Returns the freshly-persisted :ts:type:`VisaDetail` row so the host
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
=======
 * Record or update the visa outcome for an application at the visa
 * stage (E35; Journey J28; #196). Backed by
 * ``PATCH /visa/applications/{id}/outcome`` — the write-side of the
 * visa outcome flow (sibling backend ticket #195).
 *
 * The payload field shape mirrors
 * :class:`app.schemas.visa.UpdateVisaOutcomeRequest`: ``status`` is
 * the only required input on first creation, ``outcome_date`` and
 * ``notes`` are optional context. A PATCH with none of the three
 * fields is rejected at 422 — the caller has to be intentional.
 *
 * Server-side the endpoint enforces that the application is in the
 * ``visa_processing`` stage (any other stage, including the three
 * terminal states, is rejected with 422) and that
 * :class:`UpdateVisaOutcomeRequest` validation passes (status trim,
 * max-length caps). Errors propagate via the standard
 * :class:`ApiError` shape so the calling component can map them
 * to user-readable messages.
 */
export async function updateVisaOutcome(
  applicationId: number,
  payload: UpdateVisaOutcomePayload,
): Promise<VisaOutcome> {
  return apiFetch<VisaOutcome>(`/visa/applications/${applicationId}/outcome`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
>>>>>>> origin/main
  })
}
