/**
 * Analytics types (E41/E42; Journeys J34/J35).
 *
 * Supports branch manager dashboard with date-range filter (E41)
 * and owner cross-branch comparison dashboard (E42).
 */

/**
 * Query parameters for analytics APIs with optional date range filter.
 */
export interface AnalyticsParams {
  /** Filter applications created on or after this date/time (ISO 8601 format) */
  start_date?: string
  /** Filter applications created before or on this date/time (ISO 8601 format) */
  end_date?: string
}

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

/**
<<<<<<< HEAD
 * Metrics for a single tenant in platform-wide stats (E43; Journey J36).
 *
 * Represents aggregated metrics for one consultancy tenant on the platform,
 * used by Super Admins to monitor overall platform health and tenant growth.
 */
export type TenantStatsBucket = {
  /** ID of the tenant */
  tenant_id: number
  /** Name of the tenant consultancy */
  tenant_name: string
  /** URL-friendly slug identifier of the tenant */
  tenant_slug: string
  /** Subscription plan code (starter/growth/enterprise) if assigned */
  plan_code: string | null
  /** Number of branches in this tenant */
  branches_count: number
  /** Number of staff accounts in this tenant */
  staff_count: number
  /** Number of student accounts in this tenant */
  students_count: number
  /** Total number of applications in this tenant */
  applications_count: number
  /** Number of applications enrolled (terminal stage) */
  enrolled_count: number
  /** Number of applications rejected (terminal stage) */
  rejected_count: number
  /** Number of applications withdrawn (terminal stage) */
  withdrawn_count: number
  /** Number of applications still in active stages (not yet terminal) */
=======
 * Query parameters for branch comparison API.
 */
export interface BranchComparisonParams {
  start_date?: string
  end_date?: string
}

/**
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
>>>>>>> origin/main
  active_count: number
}

/**
<<<<<<< HEAD
 * Response for GET /analytics/platform-wide-stats (E43; Journey J36).
 *
 * Returns aggregated metrics for all tenants on the platform,
 * allowing Super Admins to monitor overall platform health, tenant
 * growth, and usage patterns.
 */
export type PlatformWideStatsResponse = {
  /** List of tenant metrics, ordered by applications_count descending */
  tenants: TenantStatsBucket[]
  /** Total number of tenants on the platform */
  total_tenants: number
  /** Total number of branches across all tenants */
  total_branches: number
  /** Total number of staff across all tenants */
  total_staff: number
  /** Total number of students across all tenants */
  total_students: number
  /** Total number of applications across all tenants */
=======
 * Response from GET /analytics/branch-comparison
 */
export interface BranchComparisonResponse {
  branches: BranchComparisonBucket[]
  total_branches: number
>>>>>>> origin/main
  total_applications: number
}
