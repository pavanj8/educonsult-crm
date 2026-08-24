/**
 * Analytics types (E41; Journey J34).
 *
 * Supports branch manager dashboard with date-range filter.
 */

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
  end_date?: string
}

/**
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
}
