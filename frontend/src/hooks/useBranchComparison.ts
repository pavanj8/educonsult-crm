/**
 * Custom hook for fetching branch comparison analytics (E42; Journey J35).
 */

import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchBranchComparison } from '../api/analytics'
import { hasAccessToken } from '../store/authStorage'
import type { BranchComparisonBucket, BranchComparisonParams } from '../types/analytics'

export interface UseBranchComparisonResult {
  branches: BranchComparisonBucket[]
  totalBranches: number
  totalApplications: number
  loading: boolean
  error: string | null
  reload: () => Promise<void>
  refetch: (params?: BranchComparisonParams) => Promise<void>
}

/**
 * Hook for fetching cross-branch comparison data for the consultancy owner dashboard.
 * Supports optional date range filtering and automatic refetch on mount.
 *
 * @param initialParams - Optional date range filters for the initial load
 */
export function useBranchComparison(initialParams?: BranchComparisonParams): UseBranchComparisonResult {
  const [branches, setBranches] = useState<BranchComparisonBucket[]>([])
  const [totalBranches, setTotalBranches] = useState(0)
  const [totalApplications, setTotalApplications] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentParams, setCurrentParams] = useState<BranchComparisonParams | undefined>(
    initialParams,
  )

  const loadData = useCallback(async (params?: BranchComparisonParams) => {
    if (!hasAccessToken()) {
      setBranches([])
      setTotalBranches(0)
      setTotalApplications(0)
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const response = await fetchBranchComparison(params)
      setBranches(response.branches)
      setTotalBranches(response.total_branches)
      setTotalApplications(response.total_applications)
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setError('You do not have permission to view branch analytics')
      } else if (isApiError(err) && err.status === 401) {
        setError('Sign in to view branch analytics')
      } else {
        setError('Failed to load branch comparison data')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadData(currentParams)
  }, [loadData, currentParams])

  const reload = useCallback(() => {
    return loadData(currentParams)
  }, [loadData, currentParams])

  const refetch = useCallback((params?: BranchComparisonParams) => {
    setCurrentParams(params)
    return loadData(params)
  }, [loadData])

  return { branches, totalBranches, totalApplications, loading, error, reload, refetch }
}
