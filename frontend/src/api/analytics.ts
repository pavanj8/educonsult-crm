/**
 * Analytics API client (E41/E42; Journeys J34/J35).
 *
 * Provides functions to fetch branch manager analytics data
 * (registrations-over-time, conversion funnel) and consultancy owner
 * cross-branch comparison data, with optional date range filtering.
 */

import { apiFetch } from './client'
import type {
  AnalyticsParams,
  BranchComparisonResponse,
  ConversionFunnelResponse,
  RegistrationsOverTimeResponse,
} from '../types/analytics'

/**
 * Fetch registrations-over-time data for the current user's branch.
 *
 * @param params - Optional date range filters (start_date, end_date)
 * @returns Promise resolving to registrations-over-time response
 */
export async function fetchRegistrationsOverTime(
  params?: AnalyticsParams,
): Promise<RegistrationsOverTimeResponse> {
  const searchParams = new URLSearchParams()

  if (params?.start_date) {
    searchParams.set('start_date', params.start_date)
  }

  if (params?.end_date) {
    searchParams.set('end_date', params.end_date)
  }

  const queryString = searchParams.toString()
  const path = `/analytics/registrations${queryString ? `?${queryString}` : ''}`

  return apiFetch<RegistrationsOverTimeResponse>(path)
}

/**
 * Fetch conversion funnel data for the current user's branch.
 *
 * @param params - Optional date range filters (start_date, end_date)
 * @returns Promise resolving to conversion funnel response
 */
export async function fetchConversionFunnel(
  params?: AnalyticsParams,
): Promise<ConversionFunnelResponse> {
  const searchParams = new URLSearchParams()

  if (params?.start_date) {
    searchParams.set('start_date', params.start_date)
  }

  if (params?.end_date) {
    searchParams.set('end_date', params.end_date)
  }

  const queryString = searchParams.toString()
  const path = `/analytics/funnel${queryString ? `?${queryString}` : ''}`

  return apiFetch<ConversionFunnelResponse>(path)
}

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
