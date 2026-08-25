/**
 * Analytics API client (E42; Journey J35).
 */

import { apiFetch } from './client'
import type {
  BranchComparisonBucket,
  BranchComparisonResponse,
} from '../types/analytics'

/**
 * Query parameters for branch comparison API.
 */
export interface BranchComparisonParams {
  start_date?: string
  end_date?: string
}

/**
 * Fetch cross-branch comparison data for the consultancy owner dashboard.
 * Requires consultancy_owner or super_admin role.
 *
 * @param params - Optional date range filters
 * @returns Branch comparison metrics for all branches in the consultancy
 */
export async function fetchBranchComparison(
  params?: BranchComparisonParams,
): Promise<BranchComparisonResponse> {
  const searchParams = new URLSearchParams()
  if (params?.start_date) {
    searchParams.set('start_date', params.start_date)
  }
  if (params?.end_date) {
    searchParams.set('end_date', params.end_date)
  }

  const queryString = searchParams.toString()
  const url = `/analytics/branch-comparison${queryString ? `?${queryString}` : ''}`

  const response = await apiFetch<BranchComparisonResponse>(url)
  return response
}

export type { BranchComparisonBucket, BranchComparisonResponse }
