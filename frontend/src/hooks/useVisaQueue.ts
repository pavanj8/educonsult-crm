import { useCallback, useEffect, useState } from 'react'

import { fetchVisaStageQueue } from '../api/visa'
import { isApiError } from '../api/client'
import { hasAccessToken } from '../store/authStorage'
import type { VisaStageQueueItem } from '../types/visa'

/**
 * Loads the visa-stage applications queue (E33; Journey J26; #192) for the
 * signed-in visa processor. Mirrors the loading / error / empty conventions of
 * the document-verifier queue hook (:ts:func:`useVerifierQueue`).
 */
export function useVisaQueue() {
  const [applications, setApplications] = useState<VisaStageQueueItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadQueue = useCallback(async () => {
    if (!hasAccessToken()) {
      setApplications([])
      setTotal(0)
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const queue = await fetchVisaStageQueue()
      setApplications(queue.items)
      setTotal(queue.total)
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setError('You do not have permission to view the visa queue')
      } else if (isApiError(err) && err.status === 401) {
        setError('Sign in to view the visa queue')
      } else if (err instanceof Error && err.message) {
        // Surface the backend detail (e.g. "Visa queue is temporarily
        // unavailable" on a 503 from sibling ticket #191) so the user
        // can distinguish a transient backend outage from a generic
        // client-side failure.
        setError(err.message)
      } else {
        setError('Failed to load the visa queue')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadQueue()
  }, [loadQueue])

  return { applications, total, loading, error, reload: loadQueue }
}
