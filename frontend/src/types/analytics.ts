/**
<<<<<<< HEAD
 * Analytics types for branch comparison dashboard (E42; Journey J35).
 */

/**
 * Query parameters for branch comparison API.
 */
export interface BranchComparisonParams {
  start_date?: string
=======
 * Analytics types (E41; Journey J34).
 *
 * Supports branch manager dashboard with date-range filter.
 */

/**
 * A single data point in the registrations-over-time series.
 * Represents the count of new student registrations for a specific date.
 */
export type RegistrationsOverTimeBucket = {
  /** The date bucket in ISO 8601 format (YYYY-MM-DD) */
  date: string
  /** Number of new student registrations on this date */
  count: number
}

/**
 * Response for GET /analytics/registrations.
 *
 * Returns a time-series of student registrations grouped by date,
 * ordered chronologically from oldest to newest.
 */
export type RegistrationsOverTimeResponse = {
  /** Time-series data points of registrations over time */
  data: RegistrationsOverTimeBucket[]
  /** Total number of registrations in the filtered date range */
  total_registrations: number
}

/**
 * A single stage in the conversion funnel. Represents the count of
 * applications currently at a specific pipeline stage, filtered by
 * date range and scoped to the caller's branch.
 */
export type ConversionFunnelBucket = {
  /** The pipeline stage */
  stage: string
  /** Number of applications currently at this stage */
  count: number
}

/**
 * Response for GET /analytics/funnel.
 *
 * Returns a list of buckets representing the conversion funnel by stage,
 * ordered from earliest to latest stage. Terminal stages (enrolled,
 * rejected, withdrawn) are included at the end.
 */
export type ConversionFunnelResponse = {
  /** Conversion funnel breakdown by pipeline stage */
  funnel: ConversionFunnelBucket[]
  /** Total number of applications in the filtered date range */
  total_applications: number
}

/**
 * Parameters for analytics API calls with optional date range filter.
 */
export type AnalyticsParams = {
  /** Filter applications created on or after this date/time (ISO 8601 format) */
  start_date?: string
  /** Filter applications created before or on this date/time (ISO 8601 format) */
>>>>>>> origin/main
  end_date?: string
}

/**
<<<<<<< HEAD
 * A single branch in the cross-branch comparison response.
 */
export interface BranchComparisonBucket {
  branch_id: number
  branch_name: string
  branch_city: string
  total_applications: number
  enrolled_count: number
  rejected_count: number
  withdrawn_count: number
  active_count: number
}

/**
 * Response from GET /analytics/branch-comparison
 */
export interface BranchComparisonResponse {
  branches: BranchComparisonBucket[]
  total_branches: number
  total_applications: number
=======
 * Date range preset options for the dashboard filter.
 */
export type DateRangePreset = '7d' | '15d' | '30d' | 'custom'

/**
 * Computed date range for UI display and API calls.
 */
export type DateRange = {
  preset: DateRangePreset
  startDate: string | null
  endDate: string | null
>>>>>>> origin/main
}
