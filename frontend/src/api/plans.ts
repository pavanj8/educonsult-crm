/**
 * Plan and usage API client functions (E45, E46; Journey J38, J39, E47; Journey J40).
 */

import { apiFetch } from './client'
import type { PlanAndUsage, TenantBillingStatus, UpgradeOrderResponse } from '../types/plan'

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

/**
 * Create a Razorpay order for plan upgrade/downgrade.
 *
 * This endpoint is used by the Consultancy Owner to initiate a plan change.
 * It creates a Razorpay order and returns the order details needed to
 * open the Razorpay checkout modal on the frontend.
 *
 * Endpoint: ``POST /billing/create-upgrade-order`` (E46; Journey J39).
 *
 * @param planCode - The target plan tier code (starter, growth, enterprise).
 * @returns The Razorpay order details and plan information.
 */
export async function createUpgradeOrder(
  planCode: 'starter' | 'growth' | 'enterprise'
): Promise<UpgradeOrderResponse> {
  return apiFetch<UpgradeOrderResponse>('/billing/create-upgrade-order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_code: planCode }),
  })
}

/**
 * Fetch all tenants' billing/subscription status.
 *
 * This endpoint is used by the Super Admin to view all tenants' plan
 * assignments and usage across the platform.
 *
 * Endpoint: ``GET /billing/tenant-status`` (E47; Journey J40).
 *
 * Returns a list of all tenants with their assigned plan details and
 * current usage counts. Tenants without an assigned plan are included
 * with a null plan field.
 */
export async function fetchAllTenantsBillingStatus(): Promise<TenantBillingStatus[]> {
  return apiFetch<TenantBillingStatus[]>('/billing/tenant-status')
}
