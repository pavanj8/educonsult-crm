/**
 * Branch Manager Analytics Dashboard (E41; Journey J34).
 *
 * Displays conversion funnel by stage with date-range filter.
 * Shows charts for branch-level analytics.
 */

import { useState } from 'react'

import { useAnalytics } from '../hooks/useAnalytics'
import { PIPELINE_STAGE_LABELS } from '../types/application'
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
 * Main branch manager dashboard page component.
 */
export default function BranchManagerDashboardPage() {
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

  const { data, loading, error, reload } = useAnalytics(dateRange)

  const handlePresetChange = (preset: DateRangePreset) => {
    setDateRangePreset(preset)
    if (preset !== 'custom') {
      setCustomStartDate('')
      setCustomEndDate('')
    }
  }

  return (
    <section
      className="branch-manager-dashboard"
      aria-labelledby="branch-manager-dashboard-heading"
    >
      <header className="branch-manager-dashboard__header">
        <h1 id="branch-manager-dashboard-heading">Branch Analytics Dashboard</h1>
        <button
          type="button"
          onClick={() => void reload()}
          disabled={loading}
          data-testid="reload-button"
        >
          Refresh
        </button>
      </header>

      {/* Date Range Filter */}
      <section
        className="branch-manager-dashboard__filter"
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
          Loading analytics data…
        </p>
      ) : error ? (
        <p role="alert" data-testid="analytics-error">
          {error}
        </p>
      ) : data ? (
        <div className="analytics-content" data-testid="analytics-content">
          {/* Summary Stats */}
          <section
            className="analytics-summary"
            aria-labelledby="summary-heading"
          >
            <h2 id="summary-heading" className="sr-only">
              Summary Statistics
            </h2>
            <div className="summary-cards">
              <div className="summary-card" data-testid="total-applications-card">
                <dt>Total Applications</dt>
                <dd className="summary-value" data-testid="total-applications-value">
                  {data.total_applications}
                </dd>
              </div>
              <div
                className="summary-card"
                data-testid="enrolled-applications-card"
              >
                <dt>Enrolled</dt>
                <dd className="summary-value" data-testid="enrolled-value">
                  {data.funnel.find((b) => b.stage === 'enrolled')?.count ?? 0}
                </dd>
              </div>
              <div
                className="summary-card"
                data-testid="conversion-rate-card"
              >
                <dt>Conversion Rate</dt>
                <dd className="summary-value" data-testid="conversion-rate-value">
                  {data.total_applications > 0
                    ? `${(
                        ((data.funnel.find((b) => b.stage === 'enrolled')?.count ?? 0) /
                          data.total_applications) *
                        100
                      ).toFixed(1)}%`
                    : '0%'}
                </dd>
              </div>
            </div>
          </section>

          {/* Conversion Funnel Chart */}
          <section
            className="conversion-funnel-section"
            aria-labelledby="funnel-heading"
          >
            <h2 id="funnel-heading">Conversion Funnel by Stage</h2>
            <ConversionFunnelChart funnel={data.funnel} />
          </section>
        </div>
      ) : null}
    </section>
  )
}

/**
 * Simple horizontal bar chart for conversion funnel.
 * Uses HTML/CSS for accessibility and simplicity.
 */
interface ConversionFunnelChartProps {
  funnel: Array<{ stage: string; count: number }>
}

function ConversionFunnelChart({ funnel }: ConversionFunnelChartProps) {
  const maxCount = Math.max(...funnel.map((b) => b.count), 1)

  return (
    <div className="funnel-chart" data-testid="funnel-chart">
      <table className="funnel-table">
        <caption className="sr-only">Applications by pipeline stage</caption>
        <thead>
          <tr>
            <th scope="col">Stage</th>
            <th scope="col">Count</th>
            <th scope="col" className="sr-only">
              Bar chart
            </th>
          </tr>
        </thead>
        <tbody>
          {funnel.map((bucket) => (
            <tr key={bucket.stage} data-testid={`funnel-row-${bucket.stage}`}>
              <th scope="row">
                {PIPELINE_STAGE_LABELS[bucket.stage as keyof typeof PIPELINE_STAGE_LABELS] ??
                  bucket.stage}
              </th>
              <td className="count-cell">{bucket.count}</td>
              <td className="bar-cell">
                <div
                  className="bar"
                  style={{
                    width: `${(bucket.count / maxCount) * 100}%`,
                  }}
                  aria-label={`${bucket.count} applications at ${bucket.stage} stage`}
                >
                  <span className="sr-only">
                    {bucket.count} applications at{' '}
                    {PIPELINE_STAGE_LABELS[
                      bucket.stage as keyof typeof PIPELINE_STAGE_LABELS
                    ] ?? bucket.stage}{' '}
                    stage
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
