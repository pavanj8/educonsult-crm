/**
 * Plan and usage API client functions (E45; Journey J38).
 */

import { apiFetch } from './client'
import type { PlanAndUsage } from '../types/plan'

/**
 * Fetch the current plan and usage summary for the authenticated user's tenant.
 *
 * This endpoint is used by the Consultancy Owner to view their current
 * subscription plan tier and resource usage (branches, staff, students).
 *
 * Endpoint: ``GET /me/plan-usage`` (E45; Journey J38).
 *
 * Returns the plan details (tier, limits) and current usage counts.
 * If no plan has been assigned to the tenant yet, plan will be null.
 */
export async function fetchMyPlanAndUsage(): Promise<PlanAndUsage> {
  return apiFetch<PlanAndUsage>('/me/plan-usage')
}
