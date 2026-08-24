import { apiFetch } from './client'
import type { UpdateVisaOutcomePayload, VisaOutcome, VisaStageQueue } from '../types/visa'

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
  })
}
