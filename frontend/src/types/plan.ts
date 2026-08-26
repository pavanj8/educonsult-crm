/**
 * Plan and usage types aligned with backend E45 and E46 schemas.
 *
 * These types describe the subscription plan and current usage
 * information displayed to consultancy owners on the billing/usage page
 * (E45; Journey J38) and the Razorpay checkout integration (E46; Journey J39).
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

/**
 * Response from POST /billing/create-upgrade-order (E46; Journey J39).
 *
 * Returns the Razorpay order details needed to initiate checkout on the
 * frontend. The frontend uses these values to open the Razorpay payment
 * modal.
 */
export type UpgradeOrderResponse = {
  /** Razorpay order ID for checkout. */
  order_id: string
  /** Amount in smallest currency unit (paisa for INR). */
  amount: number
  /** ISO 4217 currency code (e.g., INR). */
  currency: string
  /** Target plan tier code. */
  plan_code: 'starter' | 'growth' | 'enterprise'
  /** Human-readable plan name for display. */
  plan_name: string
  /** Razorpay key ID for checkout initialization (server-controlled). */
  razorpay_key_id: string
}

/**
 * Razorpay checkout options passed to the Razorpay SDK.
 *
 * These are the minimal required options to open the checkout modal.
 * Additional options like theme, notes, and callbacks can be added as needed.
 */
export type RazorpayCheckoutOptions = {
  /** Razorpay key ID (from backend config). */
  key: string
  /** Razorpay order ID from create-upgrade-order response. */
  order_id: string
  /** Amount in smallest currency unit (paisa for INR). */
  amount: number
  /** ISO 4217 currency code. */
  currency: string
  /** Customer name (optional, for display). */
  name?: string
  /** Customer email (optional, for display). */
  email?: string
  /** Customer contact (optional, for display). */
  contact?: string
  /** Callback invoked when payment succeeds. */
  handler: (response: RazorpayPaymentResponse) => void
  /** Callback invoked when modal is closed without payment. */
  modal?: {
    ondismiss?: () => void
  }
}

/**
 * Razorpay payment response returned by the checkout handler.
 *
 * This contains the payment ID, order ID, and signature that can be
 * sent to the backend for verification (though our webhook handler
 * processes payment confirmation automatically).
 */
export type RazorpayPaymentResponse = {
  /** Razorpay payment ID. */
  razorpay_payment_id: string
  /** Razorpay order ID. */
  razorpay_order_id: string
  /** Razorpay signature. */
  razorpay_signature: string
}

/**
 * Plan details as returned in the tenant billing status response (E47; Journey J40).
 *
 * This is a simplified view of plan data for display in the super admin
 * billing status overview. It contains the tier code, name, and limits.
 */
export type TenantPlanInfo = {
  /** Plan tier code (starter, growth, enterprise). */
  code: 'starter' | 'growth' | 'enterprise'
  /** Human-readable plan name. */
  name: string
  /** Maximum number of branches (null for unlimited). */
  max_branches: number | null
  /** Maximum number of staff accounts (null for unlimited). */
  max_staff: number | null
  /** Maximum number of student accounts (null for unlimited). */
  max_students: number | null
  /** Whether the plan is active. */
  is_active: boolean
}

/**
 * Billing status for a single tenant (E47; Journey J40).
 *
 * Returned by the GET /billing/tenant-status super admin endpoint.
 * Contains the tenant's identity, assigned plan details, and current
 * usage counts against plan caps.
 */
export type TenantBillingStatus = {
  /** The tenant's primary key. */
  tenant_id: number
  /** Human-readable tenant name. */
  tenant_name: string
  /** Tenant's URL slug. */
  tenant_slug: string
  /** The tenant's assigned plan (null if no plan assigned). */
  plan: TenantPlanInfo | null
  /** Current number of branches created by this tenant. */
  branches_used: number
  /** Current number of staff accounts (non-student roles). */
  staff_used: number
  /** Current number of student accounts. */
  students_used: number
  /** When the tenant was created. */
  created_at: string
  /** When the tenant was last updated. */
  updated_at: string
}
