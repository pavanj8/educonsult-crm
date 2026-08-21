import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchPendingDocuments, rejectDocument } from '../api/verifier'
import { hasAccessToken } from '../store/authStorage'
import type { PendingDocument } from '../types/verifier'

/**
 * Loads the document verifier's pending-document queue (E28; Journey J21),
 * mirroring the loading/error conventions of the other list hooks.
 */
export function useVerifierQueue() {
  const [documents, setDocuments] = useState<PendingDocument[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadQueue = useCallback(async () => {
    if (!hasAccessToken()) {
      setDocuments([])
      setTotal(0)
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const queue = await fetchPendingDocuments()
      setDocuments(queue.items)
      setTotal(queue.total)
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setError('You do not have permission to view the verifier queue')
      } else if (isApiError(err) && err.status === 401) {
        setError('Sign in to view the verifier queue')
      } else {
        setError('Failed to load the pending-document queue')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadQueue()
  }, [loadQueue])

  /**
   * Reject a document (E30; Journey J23). On success the row is removed from the
   * queue and the total decremented. Errors are mapped to user-readable copy and
   * re-thrown so the caller (RejectAction) can keep its form open.
   */
  const reject = useCallback(async (documentId: number, comment: string) => {
    try {
      await rejectDocument(documentId, comment)
      setDocuments((prev) => prev.filter((doc) => doc.id !== documentId))
      setTotal((prev) => Math.max(0, prev - 1))
    } catch (err) {
      if (isApiError(err) && err.status === 401) {
        throw new Error('Your session has expired — please sign in again')
      }
      if (isApiError(err) && err.status === 403) {
        throw new Error("You don't have permission to reject documents")
      }
      if (isApiError(err) && err.status === 404) {
        throw new Error('This document is no longer available')
      }
      if (isApiError(err) && err.status === 422) {
        throw new Error(err.message || 'A rejection comment is required')
      }
      throw new Error('Failed to reject the document')
    }
  }, [])

  return { documents, total, loading, error, reload: loadQueue, reject }
}
