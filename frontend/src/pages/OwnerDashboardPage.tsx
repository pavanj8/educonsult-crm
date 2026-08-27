/**
 * Consultancy Owner dashboard — cross-branch comparison view (E42; Journey J35).
 * Displays aggregated metrics for all branches in the consultancy, allowing
 * owners to compare performance across branches with optional date-range filtering.
 */

import { useState } from 'react'

import { useBranchComparison } from '../hooks/useBranchComparison'
import { ExportButton } from '../components/analytics/ExportButton'
import { getAnalyticsExportUrl } from '../api/analytics'

/**
 * Owner dashboard component with branch comparison table and date filter.
 */
export default function OwnerDashboardPage() {
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  const { branches, totalBranches, totalApplications, loading, error, reload, refetch } =
    useBranchComparison(
      startDate || endDate
        ? {
            ...(startDate && { start_date: new Date(startDate).toISOString() }),
            ...(endDate && { end_date: new Date(endDate).toISOString() }),
          }
        : undefined,
    )

  const handleFilter = () => {
    void refetch(
      startDate || endDate
        ? {
            ...(startDate && { start_date: new Date(startDate).toISOString() }),
            ...(endDate && { end_date: new Date(endDate).toISOString() }),
          }
        : undefined,
    )
  }

  const handleClear = () => {
    setStartDate('')
    setEndDate('')
    void refetch(undefined)
  }

  return (
    <section className="owner-dashboard" aria-labelledby="owner-dashboard-heading">
      <header className="owner-dashboard__header">
        <h1 id="owner-dashboard-heading">Branch comparison dashboard</h1>
        <div className="header-actions">
          <ExportButton
            endpoint={getAnalyticsExportUrl('branch-comparison', 'csv', {
              start_date: startDate ? new Date(startDate).toISOString() : undefined,
              end_date: endDate ? new Date(endDate).toISOString() : undefined,
            })}
            format="csv"
            label="Export (CSV)"
            className="export-button-branch-comparison"
            data-testid="export-branch-comparison-csv"
          />
          <button type="button" onClick={() => void reload()} disabled={loading}>
            Refresh
          </button>
        </div>
      </header>

      <div className="owner-dashboard__filters">
        <div className="owner-dashboard__filter-row">
          <label htmlFor="start-date">
            From:
            <input
              id="start-date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              data-testid="start-date-input"
            />
          </label>
          <label htmlFor="end-date">
            To:
            <input
              id="end-date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              data-testid="end-date-input"
            />
          </label>
          <button type="button" onClick={handleFilter} disabled={loading} data-testid="apply-filter">
            Apply filter
          </button>
          <button
            type="button"
            onClick={handleClear}
            disabled={loading || (!startDate && !endDate)}
            data-testid="clear-filter"
          >
            Clear
          </button>
        </div>
      </div>

      {loading ? (
        <p role="status" aria-live="polite" data-testid="branch-comparison-loading">
          Loading branch comparison data…
        </p>
      ) : error ? (
        <p role="alert" data-testid="branch-comparison-error">
          {error}
        </p>
      ) : branches.length === 0 ? (
        <p data-testid="branch-comparison-empty">No branches found for your consultancy.</p>
      ) : (
        <>
          <div className="owner-dashboard__summary" data-testid="branch-comparison-summary">
            <p>
              <strong>{totalBranches}</strong> branch{totalBranches === 1 ? '' : 'es'}
            </p>
            <p>
              <strong>{totalApplications}</strong> application{totalApplications === 1 ? '' : 's'}
            </p>
          </div>

          <table
            className="owner-dashboard__table"
            data-testid="branch-comparison-table"
            aria-label="Branch comparison metrics"
          >
            <thead>
              <tr>
                <th scope="col">Branch</th>
                <th scope="col">City</th>
                <th scope="col" className="numeric">
                  Total
                </th>
                <th scope="col" className="numeric">
                  Active
                </th>
                <th scope="col" className="numeric">
                  Enrolled
                </th>
                <th scope="col" className="numeric">
                  Rejected
                </th>
                <th scope="col" className="numeric">
                  Withdrawn
                </th>
              </tr>
            </thead>
            <tbody>
              {branches.map((branch) => (
                <tr key={branch.branch_id} data-testid={`branch-row-${branch.branch_id}`}>
                  <td>{branch.branch_name}</td>
                  <td>{branch.branch_city}</td>
                  <td className="numeric">{branch.total_applications}</td>
                  <td className="numeric">{branch.active_count}</td>
                  <td className="numeric">{branch.enrolled_count}</td>
                  <td className="numeric">{branch.rejected_count}</td>
                  <td className="numeric">{branch.withdrawn_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
