/**
 * Super Admin Platform-Wide Stats Dashboard (E43; Journey J36).
 *
 * Displays platform-wide tenant metrics including total tenants,
 * branches, staff, students, and applications. Shows a tenant list
 * with detailed metrics per tenant, ordered by application volume.
 */

import { useState } from 'react'

import { usePlatformWideStats } from '../hooks/usePlatformWideStats'
import { ExportButton } from '../components/analytics/ExportButton'
import { getAnalyticsExportUrl } from '../api/analytics'
import type { DateRange, DateRangePreset } from '../types/analytics'

/**
 * Date range preset labels for display.
 */
const DATE_RANGE_PRESET_LABELS: Record<DateRangePreset, string> = {
  '7d': 'Last 7 days',
  '15d': 'Last 15 days',
  '30d': 'Last 30 days',
  custom: 'Custom range',
}

/**
 * Calculate date range from preset.
 */
function getDateRangeFromPreset(preset: DateRangePreset): DateRange {
  const now = new Date()
  const endDate = now.toISOString().split('T')[0] // YYYY-MM-DD

  let startDate: string | null = null
  if (preset === '7d') {
    const sevenDaysAgo = new Date(now)
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
    startDate = sevenDaysAgo.toISOString().split('T')[0]
  } else if (preset === '15d') {
    const fifteenDaysAgo = new Date(now)
    fifteenDaysAgo.setDate(fifteenDaysAgo.getDate() - 15)
    startDate = fifteenDaysAgo.toISOString().split('T')[0]
  } else if (preset === '30d') {
    const thirtyDaysAgo = new Date(now)
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)
    startDate = thirtyDaysAgo.toISOString().split('T')[0]
  }

  return { preset, startDate, endDate }
}

/**
 * Main super admin dashboard page component.
 */
export default function SuperAdminDashboardPage() {
  const [dateRangePreset, setDateRangePreset] = useState<DateRangePreset>('15d')
  const [customStartDate, setCustomStartDate] = useState<string>('')
  const [customEndDate, setCustomEndDate] = useState<string>('')

  // Determine actual date range to use
  let dateRange: DateRange
  if (dateRangePreset === 'custom') {
    dateRange = {
      preset: 'custom',
      startDate: customStartDate || null,
      endDate: customEndDate || null,
    }
  } else {
    dateRange = getDateRangeFromPreset(dateRangePreset)
  }

  const { stats, loading, error, reload } = usePlatformWideStats(dateRange)

  const handlePresetChange = (preset: DateRangePreset) => {
    setDateRangePreset(preset)
    if (preset !== 'custom') {
      setCustomStartDate('')
      setCustomEndDate('')
    }
  }

  return (
    <section
      className="super-admin-dashboard"
      aria-labelledby="super-admin-dashboard-heading"
    >
      <header className="super-admin-dashboard__header">
        <h1 id="super-admin-dashboard-heading">Platform-Wide Stats Dashboard</h1>
        <div className="header-actions">
          <ExportButton
            endpoint={getAnalyticsExportUrl('platform-stats', 'csv', {
              start_date: dateRange.startDate ? new Date(dateRange.startDate).toISOString() : undefined,
              end_date: dateRange.endDate ? new Date(dateRange.endDate).toISOString() : undefined,
            })}
            format="csv"
            label="Export Stats (CSV)"
            className="export-button-platform-stats"
            data-testid="export-platform-stats-csv"
          />
          <ExportButton
            endpoint={getAnalyticsExportUrl('platform-stats', 'xlsx', {
              start_date: dateRange.startDate ? new Date(dateRange.startDate).toISOString() : undefined,
              end_date: dateRange.endDate ? new Date(dateRange.endDate).toISOString() : undefined,
            })}
            format="xlsx"
            label="Export Stats (Excel)"
            className="export-button-platform-stats-xlsx"
            data-testid="export-platform-stats-xlsx"
          />
          <button
            type="button"
            onClick={() => void reload()}
            disabled={loading}
            data-testid="reload-button"
          >
            Refresh
          </button>
        </div>
      </header>

      {/* Date Range Filter */}
      <section
        className="super-admin-dashboard__filter"
        aria-labelledby="date-range-heading"
      >
        <h2 id="date-range-heading" className="sr-only">
          Date Range Filter
        </h2>
        <div className="date-range-controls" data-testid="date-range-controls">
          <label htmlFor="preset-select" className="date-range-label">
            Date Range:
          </label>
          <select
            id="preset-select"
            className="date-range-select"
            value={dateRangePreset}
            onChange={(e) => handlePresetChange(e.target.value as DateRangePreset)}
            data-testid="preset-select"
          >
            <option value="7d">{DATE_RANGE_PRESET_LABELS['7d']}</option>
            <option value="15d">{DATE_RANGE_PRESET_LABELS['15d']}</option>
            <option value="30d">{DATE_RANGE_PRESET_LABELS['30d']}</option>
            <option value="custom">{DATE_RANGE_PRESET_LABELS.custom}</option>
          </select>

          {dateRangePreset === 'custom' && (
            <div className="custom-date-range" data-testid="custom-date-range">
              <div className="custom-date-field">
                <label htmlFor="start-date">From:</label>
                <input
                  id="start-date"
                  type="date"
                  value={customStartDate}
                  onChange={(e) => setCustomStartDate(e.target.value)}
                  className="date-input"
                  data-testid="start-date-input"
                />
              </div>
              <div className="custom-date-field">
                <label htmlFor="end-date">To:</label>
                <input
                  id="end-date"
                  type="date"
                  value={customEndDate}
                  onChange={(e) => setCustomEndDate(e.target.value)}
                  className="date-input"
                  data-testid="end-date-input"
                />
              </div>
            </div>
          )}
        </div>

        <div className="date-range-display" data-testid="date-range-display">
          {dateRange.startDate && dateRange.endDate ? (
            <p>
              Showing data from <strong>{dateRange.startDate}</strong> to{' '}
              <strong>{dateRange.endDate}</strong>
            </p>
          ) : dateRange.startDate ? (
            <p>
              Showing data from <strong>{dateRange.startDate}</strong> onwards
            </p>
          ) : dateRange.endDate ? (
            <p>
              Showing data up to <strong>{dateRange.endDate}</strong>
            </p>
          ) : (
            <p>All available data</p>
          )}
        </div>
      </section>

      {/* Analytics Content */}
      {loading ? (
        <p role="status" aria-live="polite" data-testid="analytics-loading">
          Loading platform stats…
        </p>
      ) : error ? (
        <p role="alert" data-testid="analytics-error">
          {error}
        </p>
      ) : stats ? (
        <div className="analytics-content" data-testid="analytics-content">
          {/* Platform Summary Stats */}
          <section
            className="platform-summary"
            aria-labelledby="platform-summary-heading"
          >
            <h2 id="platform-summary-heading" className="sr-only">
              Platform Summary Statistics
            </h2>
            <div className="summary-cards">
              <div className="summary-card" data-testid="total-tenants-card">
                <dt>Total Tenants</dt>
                <dd className="summary-value" data-testid="total-tenants-value">
                  {stats.total_tenants}
                </dd>
              </div>
              <div className="summary-card" data-testid="total-branches-card">
                <dt>Total Branches</dt>
                <dd className="summary-value" data-testid="total-branches-value">
                  {stats.total_branches}
                </dd>
              </div>
              <div className="summary-card" data-testid="total-staff-card">
                <dt>Total Staff</dt>
                <dd className="summary-value" data-testid="total-staff-value">
                  {stats.total_staff}
                </dd>
              </div>
              <div className="summary-card" data-testid="total-students-card">
                <dt>Total Students</dt>
                <dd className="summary-value" data-testid="total-students-value">
                  {stats.total_students}
                </dd>
              </div>
              <div className="summary-card" data-testid="total-applications-card">
                <dt>Total Applications</dt>
                <dd className="summary-value" data-testid="total-applications-value">
                  {stats.total_applications}
                </dd>
              </div>
            </div>
          </section>

          {/* Tenant List Table */}
          <section
            className="tenant-list-section"
            aria-labelledby="tenant-list-heading"
          >
            <h2 id="tenant-list-heading">Tenant Details</h2>
            <TenantTable tenants={stats.tenants} />
          </section>
        </div>
      ) : null}
    </section>
  )
}

/**
 * Table displaying tenant metrics.
 */
interface TenantTableProps {
  tenants: Array<{
    tenant_id: number
    tenant_name: string
    tenant_slug: string
    plan_code: string | null
    branches_count: number
    staff_count: number
    students_count: number
    applications_count: number
    enrolled_count: number
    rejected_count: number
    withdrawn_count: number
    active_count: number
  }>
}

function TenantTable({ tenants }: TenantTableProps) {
  if (tenants.length === 0) {
    return <p data-testid="no-tenants">No tenants found</p>
  }

  return (
    <div className="tenant-table-container" data-testid="tenant-table">
      <table className="tenant-table">
        <caption className="sr-only">Platform-wide tenant metrics</caption>
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
            <th scope="col" className="numeric-cell">
              Applications
            </th>
            <th scope="col" className="numeric-cell">
              Enrolled
            </th>
            <th scope="col" className="numeric-cell">
              Active
            </th>
          </tr>
        </thead>
        <tbody>
          {tenants.map((tenant) => (
            <tr key={tenant.tenant_id} data-testid={`tenant-row-${tenant.tenant_id}`}>
              <th scope="row" className="text-cell">
                <div className="tenant-name">{tenant.tenant_name}</div>
                <div className="tenant-slug text-muted">{tenant.tenant_slug}</div>
              </th>
              <td className="plan-cell">
                {tenant.plan_code ? (
                  <span className="plan-badge" data-testid={`plan-${tenant.tenant_id}`}>
                    {tenant.plan_code}
                  </span>
                ) : (
                  <span className="text-muted">—</span>
                )}
              </td>
              <td className="numeric-cell" data-testid={`branches-${tenant.tenant_id}`}>
                {tenant.branches_count}
              </td>
              <td className="numeric-cell" data-testid={`staff-${tenant.tenant_id}`}>
                {tenant.staff_count}
              </td>
              <td className="numeric-cell" data-testid={`students-${tenant.tenant_id}`}>
                {tenant.students_count}
              </td>
              <td className="numeric-cell" data-testid={`applications-${tenant.tenant_id}`}>
                {tenant.applications_count}
              </td>
              <td className="numeric-cell" data-testid={`enrolled-${tenant.tenant_id}`}>
                {tenant.enrolled_count}
              </td>
              <td className="numeric-cell" data-testid={`active-${tenant.tenant_id}`}>
                {tenant.active_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
