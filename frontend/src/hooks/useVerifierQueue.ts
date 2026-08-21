import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchPendingDocuments } from '../api/verifier'
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

  return { documents, total, loading, error, reload: loadQueue }
}
