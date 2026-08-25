/**
 * Analytics API client (E41, E42, E43; Journeys J34, J35, J36).
 *
 * Provides functions to fetch branch manager analytics data,
 * owner cross-branch comparison data, and super admin platform-wide
 * stats with optional date range filtering.
 */

import { apiFetch } from './client'
import type {
  AnalyticsParams,
  BranchComparisonResponse,
  ConversionFunnelResponse,
  PlatformWideStatsResponse,
  RegistrationsOverTimeResponse,
} from '../types/analytics'
import type { BranchComparisonParams } from '../types/analytics'

// Re-export types that are used by other modules
export type { BranchComparisonParams }

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

/**
 * Export student list as CSV or Excel (E44; Journey J37).
 *
 * This function returns a URL that can be used with the ExportButton component
 * or similar to trigger a browser download.
 *
 * @param format - Export format: 'csv' or 'xlsx'
 * @param params - Optional date range filters (start_date, end_date)
 * @returns The API endpoint URL for the export request
 */
export function getStudentListExportUrl(
  format: 'csv' | 'xlsx' = 'csv',
  params?: AnalyticsParams,
): string {
  const searchParams = new URLSearchParams()
  searchParams.set('format', format)

  if (params?.start_date) {
    searchParams.set('start_date', params.start_date)
  }

  if (params?.end_date) {
    searchParams.set('end_date', params.end_date)
  }

  const queryString = searchParams.toString()
  return `/analytics/export/students${queryString ? `?${queryString}` : ''}`
}

/**
 * Export analytics data as CSV or Excel (E44; Journey J37).
 *
 * This function returns a URL that can be used with the ExportButton component
 * or similar to trigger a browser download.
 *
 * @param exportType - Type of analytics export: 'funnel' or 'registrations' or 'branch-comparison' or 'platform-stats'
 * @param format - Export format: 'csv' or 'xlsx'
 * @param params - Optional date range filters (start_date, end_date)
 * @returns The API endpoint URL for the export request
 */
export function getAnalyticsExportUrl(
  exportType: 'funnel' | 'registrations' | 'branch-comparison' | 'platform-stats',
  format: 'csv' | 'xlsx' = 'csv',
  params?: AnalyticsParams,
): string {
  const searchParams = new URLSearchParams()
  searchParams.set('format', format)

  if (params?.start_date) {
    searchParams.set('start_date', params.start_date)
  }

  if (params?.end_date) {
    searchParams.set('end_date', params.end_date)
  }

  const queryString = searchParams.toString()

  const endpoints = {
    funnel: '/analytics/export/funnel',
    registrations: '/analytics/export/registrations',
    'branch-comparison': '/analytics/export/branch-comparison',
    'platform-stats': '/analytics/export/platform-stats',
  }

  return `${endpoints[exportType]}${queryString ? `?${queryString}` : ''}`
}
