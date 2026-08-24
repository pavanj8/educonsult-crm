import { useCallback, useEffect, useState } from 'react'

import { fetchVisaStageQueue } from '../api/visa'
import { isApiError } from '../api/client'
import { hasAccessToken } from '../store/authStorage'
import type { VisaOutcome, VisaStageQueueItem } from '../types/visa'

/**
 * Loads the visa-stage applications queue (E33; Journey J26; #192) for the
 * signed-in visa processor. Mirrors the loading / error / empty conventions of
 * the document-verifier queue hook (:ts:func:`useVerifierQueue`).
 *
 * Also tracks visa outcomes recorded during the session
 * (E35; Journey J28; #196): :data:`VisaOutcome` is a 1:1-per-application row
 * persisted via ``PATCH /visa/applications/{id}/outcome`` (sibling backend
 * ticket #195). The backend doesn't expose a per-application ``GET`` for it,
 * so the dashboard builds up an in-memory ``outcomes`` map as the visa
 * processor records / updates them in this session. The map is purely
 * UI-side: it lets the row switch its button label from "Record outcome" to
 * "Update outcome" without a refetch, and lets the action prefilled form
 * remember the last saved status / date / notes.
 */
export function useVisaQueue() {
  const [applications, setApplications] = useState<VisaStageQueueItem[]>([])
  const [total, setTotal] = useState(0)
  const [outcomes, setOutcomes] = useState<Record<number, VisaOutcome>>({})
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

  /**
   * Record a successful visa outcome PATCH (E35; Journey J28; #196) so the
   * host row can re-render with "Update outcome" + a prefilled form on the
   * next open. Called from :ts:comp:`VisaOutcomeAction`'s ``onUpdated``
   * callback.
   */
  const rememberOutcome = useCallback((outcome: VisaOutcome) => {
    setOutcomes((prev) => ({ ...prev, [outcome.application_id]: outcome }))
  }, [])

  return {
    applications,
    total,
    outcomes,
    loading,
    error,
    reload: loadQueue,
    rememberOutcome,
  }
}
