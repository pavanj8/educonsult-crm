import { useCallback, useEffect, useState } from 'react'

import {
  fetchCounselorQueue,
  fetchCounselorQueueCounts,
} from '../api/counselor'
import type { ApplicationWithStudent, CounselorQueueFilter, PipelineStage, StageCount } from '../types/application'

interface UseCounselorQueueResult {
  applications: ApplicationWithStudent[]
  loading: boolean
  error: string | null
  counts: StageCount
  countsLoading: boolean
  filter: CounselorQueueFilter
  setFilter: (filter: CounselorQueueFilter) => void
  refetch: () => Promise<void>
}

export function useCounselorQueue(): UseCounselorQueueResult {
  const [applications, setApplications] = useState<ApplicationWithStudent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [counts, setCounts] = useState<StageCount>({})
  const [countsLoading, setCountsLoading] = useState(true)
  const [filter, setFilter] = useState<CounselorQueueFilter>({})

  const loadQueue = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchCounselorQueue(filter)
      setApplications(data)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to load queue')
      }
    } finally {
      setLoading(false)
    }
  }, [filter])

  const loadCounts = useCallback(async () => {
    setCountsLoading(true)
    try {
      const data = await fetchCounselorQueueCounts()
      setCounts(data)
    } catch {
      // Counts are not critical, silently fail
    } finally {
      setCountsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadQueue()
    void loadCounts()
  }, [loadQueue, loadCounts])

  return {
    applications,
    loading,
    error,
    counts,
    countsLoading,
    filter,
    setFilter,
    refetch: loadQueue,
  }
}
