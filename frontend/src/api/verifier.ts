import { apiFetch } from './client'
import type { PendingDocumentQueue, VerifiedDocument } from '../types/verifier'

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

/**
 * Reject a pending document with a REQUIRED comment (E30; Journey J23; #184).
 * Backed by ``POST /verifier/documents/{document_id}/reject``.
 */
export async function rejectDocument(
  documentId: number,
  comment: string,
): Promise<VerifiedDocument> {
  return apiFetch<VerifiedDocument>(`/verifier/documents/${documentId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  })
}

/**
 * Approve a pending document with an OPTIONAL comment (E29; Journey J22; #181).
 * Backed by ``POST /verifier/documents/{document_id}/approve``.
 */
export async function approveDocument(
  documentId: number,
  comment?: string,
): Promise<VerifiedDocument> {
  return apiFetch<VerifiedDocument>(`/verifier/documents/${documentId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ comment: comment && comment.trim() ? comment.trim() : null }),
  })
}
