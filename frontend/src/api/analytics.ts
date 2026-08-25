/**
 * Analytics API client (E41, E42, E43; Journey J34, J35, J36).
 *
 * Provides functions to fetch branch manager analytics data,
 * owner cross-branch comparison data, and super admin platform-wide
 * stats with optional date range filtering.
 */

import { apiFetch } from './client'
import type {
  AnalyticsParams,
  ConversionFunnelResponse,
  RegistrationsOverTimeResponse,
  PlatformWideStatsResponse,
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
 * Fetch platform-wide stats for super admin view.
 *
 * @param params - Optional date range filters (start_date, end_date)
 * @returns Promise resolving to platform-wide stats response
 */
export async function fetchPlatformWideStats(
  params?: AnalyticsParams,
): Promise<PlatformWideStatsResponse> {
  const searchParams = new URLSearchParams()

  if (params?.start_date) {
    searchParams.set('start_date', params.start_date)
  }

  if (params?.end_date) {
    searchParams.set('end_date', params.end_date)
  }

  const queryString = searchParams.toString()
  const path = `/analytics/platform-wide-stats${queryString ? `?${queryString}` : ''}`

  return apiFetch<PlatformWideStatsResponse>(path)
}
