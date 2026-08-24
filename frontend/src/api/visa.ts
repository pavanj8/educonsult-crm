import { apiFetch } from './client'
import type { VisaStageQueue } from '../types/visa'

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
