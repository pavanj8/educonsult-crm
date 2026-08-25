/**
 * Custom hook for platform-wide stats (E43; Journey J36).
 *
 * Fetches and caches platform-wide tenant metrics from the analytics API.
 * Supports date-range filtering and automatic refetching.
 */

import { useCallback, useEffect, useState, useMemo } from 'react'

import { fetchPlatformWideStats } from '../api/analytics'
import type { AnalyticsParams, DateRange, PlatformWideStatsResponse } from '../types/analytics'

interface UsePlatformWideStatsResult {
  stats: PlatformWideStatsResponse | null
  loading: boolean
  error: string | null
  reload: () => Promise<void>
}

/**
 * Hook for fetching platform-wide stats with optional date range filtering.
 *
 * @param dateRange - Optional date range filter for applications/students
 * @returns Object containing stats data, loading state, error, and reload function
 */
export function usePlatformWideStats(dateRange?: DateRange): UsePlatformWideStatsResult {
  const [stats, setStats] = useState<PlatformWideStatsResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Convert DateRange to AnalyticsParams
  const params = useMemo<AnalyticsParams | undefined>(() => {
    if (!dateRange?.startDate && !dateRange?.endDate) {
      return undefined
    }
    return {
      start_date: dateRange.startDate ?? undefined,
      end_date: dateRange.endDate ?? undefined,
    }
  }, [dateRange])

  const fetchStats = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchPlatformWideStats(params)
      setStats(data)
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch platform stats'
      setError(errorMessage)
      setStats(null)
    } finally {
      setLoading(false)
    }
  }, [params])

  // Fetch stats on mount and when params change
  useEffect(() => {
    void fetchStats()
  }, [fetchStats])

  const reload = useCallback(async () => {
    await fetchStats()
  }, [fetchStats])

  return { stats, loading, error, reload }
}
