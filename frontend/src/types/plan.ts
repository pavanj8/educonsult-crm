/**
 * Plan and usage types aligned with backend E45 schemas.
 *
 * These types describe the subscription plan and current usage
 * information displayed to consultancy owners on the billing/usage page
 * (E45; Journey J38).
 */

/**
 * Usage counts for a tenant's resources.
 * Represents current consumption against plan limits.
 */
export type TenantUsage = {
  /** Number of branches created by this tenant. */
  branches: number
  /** Number of staff accounts (non-student users) in this tenant. */
  staff: number
  /** Number of student accounts in this tenant. */
  students: number
}

/**
 * Plan tier information with limits.
 * Mirrors backend PlanResponse from tenant schema.
 */
export type PlanInfo = {
  id: number
  code: 'starter' | 'growth' | 'enterprise'
  name: string
  max_branches: number | null
  max_staff: number | null
  max_students: number | null
  is_active: boolean
}

/**
 * Combined plan and usage response for a tenant.
 * This is the shape returned by the E45 backend endpoint that
 * provides both the plan details and current usage counts.
 */
export type PlanAndUsage = {
  /** The tenant's assigned plan (null if no plan assigned yet). */
  plan: PlanInfo | null
  /** Current usage counts for this tenant. */
  usage: TenantUsage
}
