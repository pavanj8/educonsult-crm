/**
 * Analytics types for branch comparison dashboard (E42; Journey J35).
 */

/**
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
  active_count: number
}

/**
 * Response from GET /analytics/branch-comparison
 */
export interface BranchComparisonResponse {
  branches: BranchComparisonBucket[]
  total_branches: number
  total_applications: number
}
