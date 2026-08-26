/**
 * Super Admin Billing Status Overview (E47; Journey J40).
 *
 * Displays all tenants' subscription plan assignments and current usage
 * across the platform. This helps the super admin monitor which tenants
 * are on which plans and how close they are to their limits.
 */

import { useAllTenantsBillingStatus } from '../hooks/useAllTenantsBillingStatus'

/**
 * Format a date string for display.
 */
function formatDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Format a plan code for display with capitalization.
 */
function formatPlanCode(code: string): string {
  return code.charAt(0).toUpperCase() + code.slice(1)
}

/**
 * Check if usage is at or near the limit.
 */
function isAtOrNearLimit(current: number, limit: number | null): boolean {
  if (limit === null) return false // Unlimited
  return current >= limit
}

function isNearLimit(current: number, limit: number | null): boolean {
  if (limit === null) return false // Unlimited
  return current >= limit * 0.8 && current < limit
}

/**
 * Main billing status page component.
 */
export default function BillingStatusPage() {
  const { tenants, loading, error, reload } = useAllTenantsBillingStatus()

  return (
    <section
      className="billing-status-page"
      aria-labelledby="billing-status-heading"
      data-testid="billing-status-page"
    >
      <header className="billing-status-page__header">
        <h1 id="billing-status-heading">Tenant Billing Status</h1>
        <p className="billing-status-page__subtitle">
          View all tenants' subscription plans and resource usage.
        </p>
        <button
          type="button"
          onClick={() => void reload()}
          disabled={loading}
          data-testid="reload-button"
        >
          Refresh
        </button>
      </header>

      {loading ? (
        <p
          role="status"
          aria-live="polite"
          data-testid="billing-status-loading"
        >
          Loading tenant billing status…
        </p>
      ) : error ? (
        <p
          role="alert"
          className="billing-status-page__error"
          data-testid="billing-status-error"
        >
          {error}
        </p>
      ) : tenants.length === 0 ? (
        <p data-testid="no-tenants">No tenants found.</p>
      ) : (
        <div className="billing-status-table-wrapper">
          <table
            className="billing-status-table"
            data-testid="billing-status-table"
          >
            <thead>
              <tr>
                <th scope="col">Tenant</th>
                <th scope="col">Plan</th>
                <th scope="col" className="numeric-cell">
                  Branches
                </th>
                <th scope="col" className="numeric-cell">
                  Staff
                </th>
                <th scope="col" className="numeric-cell">
                  Students
                </th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((tenant) => (
                <tr
                  key={tenant.tenant_id}
                  data-testid={`tenant-row-${tenant.tenant_id}`}
                >
                  <th scope="row" className="text-cell">
                    <div className="tenant-name">{tenant.tenant_name}</div>
                    <div className="tenant-slug text-muted">{tenant.tenant_slug}</div>
                  </th>
                  <td className="plan-cell">
                    {tenant.plan ? (
                      <span
                        className={`plan-badge plan-badge--${tenant.plan.code}`}
                        data-testid={`plan-${tenant.tenant_id}`}
                      >
                        {formatPlanCode(tenant.plan.code)}
                      </span>
                    ) : (
                      <span className="text-muted" data-testid={`plan-${tenant.tenant_id}`}>
                        —
                      </span>
                    )}
                  </td>
                  <td
                    className={`numeric-cell ${
                      isAtOrNearLimit(tenant.branches_used, tenant.plan?.max_branches ?? null)
                        ? 'at-limit'
                        : isNearLimit(tenant.branches_used, tenant.plan?.max_branches ?? null)
                          ? 'near-limit'
                          : ''
                    }`}
                    data-testid={`branches-${tenant.tenant_id}`}
                  >
                    {tenant.branches_used}
                    {tenant.plan && (
                      <span className="usage-limit">
                        {' '}
                        / {tenant.plan.max_branches === null ? '∞' : tenant.plan.max_branches}
                      </span>
                    )}
                  </td>
                  <td
                    className={`numeric-cell ${
                      isAtOrNearLimit(tenant.staff_used, tenant.plan?.max_staff ?? null)
                        ? 'at-limit'
                        : isNearLimit(tenant.staff_used, tenant.plan?.max_staff ?? null)
                          ? 'near-limit'
                          : ''
                    }`}
                    data-testid={`staff-${tenant.tenant_id}`}
                  >
                    {tenant.staff_used}
                    {tenant.plan && (
                      <span className="usage-limit">
                        {' '}
                        / {tenant.plan.max_staff === null ? '∞' : tenant.plan.max_staff}
                      </span>
                    )}
                  </td>
                  <td
                    className={`numeric-cell ${
                      isAtOrNearLimit(tenant.students_used, tenant.plan?.max_students ?? null)
                        ? 'at-limit'
                        : isNearLimit(tenant.students_used, tenant.plan?.max_students ?? null)
                          ? 'near-limit'
                          : ''
                    }`}
                    data-testid={`students-${tenant.tenant_id}`}
                  >
                    {tenant.students_used}
                    {tenant.plan && (
                      <span className="usage-limit">
                        {' '}
                        / {tenant.plan.max_students === null ? '∞' : tenant.plan.max_students}
                      </span>
                    )}
                  </td>
                  <td className="date-cell" data-testid={`created-${tenant.tenant_id}`}>
                    {formatDate(tenant.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
