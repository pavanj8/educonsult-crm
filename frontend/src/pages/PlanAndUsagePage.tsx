/**
 * Plan and usage page for Consultancy Owners (E45; Journey J38).
 *
 * This page displays the consultancy's current subscription plan tier,
 * plan limits, and current usage counts (branches, staff, students).
 * It helps owners understand their resource consumption and plan limits.
 */

import { usePlanAndUsage } from '../hooks/usePlanAndUsage'

/**
 * Helper component to display a single resource usage metric.
 * Shows the current count, limit (if applicable), and a visual indicator.
 */
function UsageMetric({
  label,
  current,
  limit,
  testId,
}: {
  label: string
  current: number
  limit: number | null
  testId: string
}) {
  // For unlimited plans (limit is null), show "Unlimited"
  const limitText = limit === null ? 'Unlimited' : limit.toString()
  const isUnlimited = limit === null
  const atLimit = !isUnlimited && current >= limit
  const nearLimit = !isUnlimited && !atLimit && current >= (limit * 0.8)

  // Calculate percentage for progress bar (capped at 100%)
  const percentage = isUnlimited ? 0 : (current / limit) * 100

  return (
    <div
      className="plan-usage__metric"
      data-testid={testId}
    >
      <div className="plan-usage__metric-header">
        <span className="plan-usage__metric-label">{label}</span>
        <span className="plan-usage__metric-value">
          {current} / {limitText}
        </span>
      </div>
      {!isUnlimited && (
        <div className="plan-usage__progress-bar">
          <div
            className={`plan-usage__progress-fill ${atLimit ? 'plan-usage__progress-fill--at-limit' : ''} ${nearLimit ? 'plan-usage__progress-fill--near-limit' : ''}`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
            aria-label={`${label}: ${current} of ${limit} used (${Math.round(percentage)}%)`}
          />
        </div>
      )}
      {atLimit && (
        <p className="plan-usage__warning" data-testid={`${testId}-at-limit`}>
          At limit – upgrade to add more {label.toLowerCase()}.
        </p>
      )}
    </div>
  )
}

/**
 * Plan and usage page component.
 *
 * Displays the current subscription plan tier, description, and limits,
 * along with current usage metrics for branches, staff, and students.
 * Shows appropriate messaging when no plan is assigned.
 */
export default function PlanAndUsagePage() {
  const { planAndUsage, loading, error, reload } = usePlanAndUsage()

  return (
    <section
      className="plan-usage"
      aria-labelledby="plan-usage-heading"
    >
      <header className="plan-usage__header">
        <h1 id="plan-usage-heading">Plan & usage</h1>
        <button
          type="button"
          onClick={() => void reload()}
          disabled={loading}
          data-testid="plan-usage-refresh"
        >
          Refresh
        </button>
      </header>

      {loading ? (
        <p
          role="status"
          aria-live="polite"
          data-testid="plan-usage-loading"
        >
          Loading plan and usage data…
        </p>
      ) : error ? (
        <p
          role="alert"
          data-testid="plan-usage-error"
        >
          {error}
        </p>
      ) : planAndUsage === null ? (
        <p data-testid="plan-usage-no-data">
          Unable to load plan and usage information.
        </p>
      ) : (
        <>
          {/* Plan Information Section */}
          <section
            className="plan-usage__section"
            aria-labelledby="plan-info-heading"
          >
            <h2 id="plan-info-heading">Current plan</h2>
            {planAndUsage.plan === null ? (
              <div
                className="plan-usage__no-plan"
                data-testid="plan-usage-no-plan"
              >
                <p className="plan-usage__no-plan-message">
                  No plan has been assigned to your consultancy yet.
                </p>
                <p className="plan-usage__no-plan-detail">
                  Please contact the platform administrator to assign a subscription plan.
                </p>
              </div>
            ) : (
              <div
                className="plan-usage__plan-card"
                data-testid="plan-usage-plan-card"
              >
                <div className="plan-usage__plan-header">
                  <h3
                    className="plan-usage__plan-name"
                    data-testid="plan-usage-plan-name"
                  >
                    {planAndUsage.plan.name}
                  </h3>
                  <span
                    className={`plan-usage__plan-badge plan-usage__plan-badge--${planAndUsage.plan.code}`}
                    data-testid="plan-usage-plan-code"
                  >
                    {planAndUsage.plan.code}
                  </span>
                </div>

                {/* Usage Metrics */}
                <div className="plan-usage__metrics">
                  <UsageMetric
                    label="Branches"
                    current={planAndUsage.usage.branches}
                    limit={planAndUsage.plan.max_branches}
                    testId="plan-usage-branches"
                  />
                  <UsageMetric
                    label="Staff"
                    current={planAndUsage.usage.staff}
                    limit={planAndUsage.plan.max_staff}
                    testId="plan-usage-staff"
                  />
                  <UsageMetric
                    label="Students"
                    current={planAndUsage.usage.students}
                    limit={planAndUsage.plan.max_students}
                    testId="plan-usage-students"
                  />
                </div>
              </div>
            )}
          </section>

          {/* Plan Limits Reference Section */}
          {planAndUsage.plan !== null && (
            <section
              className="plan-usage__section"
              aria-labelledby="plan-limits-heading"
            >
              <h2 id="plan-limits-heading">Plan limits</h2>
              <dl className="plan-usage__limits-list" data-testid="plan-usage-limits">
                <div className="plan-usage__limits-item">
                  <dt>Maximum branches:</dt>
                  <dd data-testid="limit-max-branches">
                    {planAndUsage.plan.max_branches === null
                      ? 'Unlimited'
                      : planAndUsage.plan.max_branches.toString()}
                  </dd>
                </div>
                <div className="plan-usage__limits-item">
                  <dt>Maximum staff:</dt>
                  <dd data-testid="limit-max-staff">
                    {planAndUsage.plan.max_staff === null
                      ? 'Unlimited'
                      : planAndUsage.plan.max_staff.toString()}
                  </dd>
                </div>
                <div className="plan-usage__limits-item">
                  <dt>Maximum students:</dt>
                  <dd data-testid="limit-max-students">
                    {planAndUsage.plan.max_students === null
                      ? 'Unlimited'
                      : planAndUsage.plan.max_students.toString()}
                  </dd>
                </div>
              </dl>
            </section>
          )}
        </>
      )}
    </section>
  )
}
