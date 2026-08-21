import { apiFetch } from './client'
import type { PendingDocumentQueue } from '../types/verifier'

export interface PendingDocumentsParams {
  limit?: number
  offset?: number
}

/**
 * Fetch the authenticated document verifier's pending-document queue
 * (E28; Journey J21). Backed by ``GET /verifier/documents/pending``.
 */
export async function fetchPendingDocuments(
  params: PendingDocumentsParams = {},
): Promise<PendingDocumentQueue> {
  const query = new URLSearchParams()
  if (params.limit != null) {
    query.set('limit', String(params.limit))
  }
  if (params.offset != null) {
    query.set('offset', String(params.offset))
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiFetch<PendingDocumentQueue>(`/verifier/documents/pending${suffix}`)
}
