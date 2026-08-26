/**
 * Custom hook for fetching plan and usage data (E45; Journey J38).
 */

import { useEffect, useState } from 'react'

import { fetchMyPlanAndUsage } from '../api/plans'
import type { PlanAndUsage } from '../types/plan'

interface UsePlanAndUsageState {
  planAndUsage: PlanAndUsage | null
  loading: boolean
  error: string | null
  reload: () => Promise<void>
  refetch: () => Promise<void>
}

/**
 * Hook to fetch the authenticated user's tenant plan and usage.
 *
 * This hook calls the backend endpoint GET /me/plan-usage on mount
 * and provides the plan details (tier, limits) along with current
 * usage counts (branches, staff, students).
 *
 * The hook handles loading, error, and retry states automatically.
 * Callers can use `reload()` to refresh the data or `refetch(data)`
 * to fetch with optional parameters (currently unused but kept
 * for consistency with other hooks).
 */
export function usePlanAndUsage(): UsePlanAndUsageState {
  const [state, setState] = useState<{
    planAndUsage: PlanAndUsage | null
    loading: boolean
    error: string | null
  }>({
    planAndUsage: null,
    loading: true,
    error: null,
  })

  const fetch = async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const data = await fetchMyPlanAndUsage()
      setState({ planAndUsage: data, loading: false, error: null })
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load plan and usage data'
      setState({ planAndUsage: null, loading: false, error: message })
    }
  }

  // Fetch on mount
  useEffect(() => {
    void fetch()
  }, [])

  const reload = async () => {
    await fetch()
  }

  const refetch = async () => {
    await fetch()
  }

  return { ...state, reload, refetch }
}
