import { useCallback, useState } from 'react'

import { isApiError } from '../api/client'
import { STAGE_COLORS, STAGE_LABELS, type PipelineStage } from '../types/application'
import { useCounselorQueue } from '../hooks/useCounselorQueue'

const PIPELINE_STAGE_ORDER: PipelineStage[] = [
  'registered',
  'counseling',
  'university_shortlisting',
  'application_submitted',
  'document_verification',
  'offer_letter',
  'visa_processing',
  'loan_processing',
]

const ACTIVE_STAGES = PIPELINE_STAGE_ORDER

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export default function CounselorDashboardPage() {
  const {
    applications,
    loading,
    error,
    counts,
    filter,
    setFilter,
    refetch,
  } = useCounselorQueue()

  const [searchValue, setSearchValue] = useState(filter.search ?? '')
  const [selectedStage, setSelectedStage] = useState<PipelineStage | ''>(filter.stage ?? '')

  const totalCount = Object.values(counts).reduce((sum, count) => sum + count, 0)

  const handleSearchChange = useCallback((value: string) => {
    setSearchValue(value)
    setFilter(prev => ({ ...prev, search: value || undefined }))
  }, [setFilter])

  const handleStageFilterChange = useCallback((value: PipelineStage | '') => {
    setSelectedStage(value)
    setFilter(prev => ({ ...prev, stage: value || undefined }))
  }, [setFilter])

  const handleClearFilters = useCallback(() => {
    setSearchValue('')
    setSelectedStage('')
    setFilter({})
  }, [setFilter])

  return (
    <div className="counselor-dashboard" data-testid="counselor-dashboard">
      <header className="counselor-dashboard__header">
        <h2>My Student Queue</h2>
        <p className="counselor-dashboard__subtitle">
          Manage your assigned students and track their applications through the pipeline.
        </p>
      </header>

      <section className="counselor-dashboard__filters" aria-label="Queue filters">
        <div className="counselor-dashboard__search">
          <label htmlFor="queue-search" className="visually-hidden">
            Search students by name or email
          </label>
          <input
            id="queue-search"
            data-testid="queue-search"
            type="search"
            placeholder="Search by student name or email..."
            value={searchValue}
            onChange={(e) => void handleSearchChange(e.target.value)}
            className="counselor-dashboard__search-input"
          />
        </div>

        <div className="counselor-dashboard__stage-filters">
          <label htmlFor="stage-filter" className="visually-hidden">
            Filter by pipeline stage
          </label>
          <select
            id="stage-filter"
            data-testid="stage-filter"
            value={selectedStage}
            onChange={(e) => void handleStageFilterChange(e.target.value as PipelineStage | '')}
            className="counselor-dashboard__stage-select"
          >
            <option value="">All Stages</option>
            {ACTIVE_STAGES.map((stage) => (
              <option key={stage} value={stage}>
                {STAGE_LABELS[stage]}
              </option>
            ))}
          </select>
        </div>

        {(searchValue || selectedStage) && (
          <button
            data-testid="clear-filters"
            type="button"
            onClick={handleClearFilters}
            className="counselor-dashboard__clear-filters"
          >
            Clear filters
          </button>
        )}
      </section>

      <section className="counselor-dashboard__stage-badges" aria-label="Stage counts">
        <div className="counselor-dashboard__total-count">
          <span className="counselor-dashboard__total-label">Total:</span>
          <span className="counselor-dashboard__total-value" data-testid="total-count">
            {totalCount}
          </span>
        </div>
        {!loading && Object.entries(counts).map(([stage, count]) => (
          <button
            key={stage}
            data-testid={`stage-badge-${stage}`}
            type="button"
            className={`counselor-dashboard__stage-badge ${
              selectedStage === stage ? 'counselor-dashboard__stage-badge--active' : ''
            }`}
            style={{
              '--badge-color': STAGE_COLORS[stage as PipelineStage],
            } as React.CSSProperties}
            onClick={() => void handleStageFilterChange(
              selectedStage === stage ? '' : (stage as PipelineStage)
            )}
          >
            <span className="counselor-dashboard__stage-name">
              {STAGE_LABELS[stage as PipelineStage]}
            </span>
            <span className="counselor-dashboard__stage-count">
              {count}
            </span>
          </button>
        ))}
      </section>

      {error && (
        <div className="counselor-dashboard__error" role="alert">
          <p data-testid="queue-error">{error}</p>
          <button
            data-testid="retry-button"
            type="button"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </div>
      )}

      {loading && <p className="counselor-dashboard__loading" data-testid="queue-loading">Loading queue...</p>}

      {!loading && !error && applications.length === 0 && (
        <div className="counselor-dashboard__empty" data-testid="queue-empty">
          <p>
            {filter.stage || filter.search
              ? 'No applications match your filters.'
              : 'No applications assigned to you yet.'}
          </p>
        </div>
      )}

      {!loading && !error && applications.length > 0 && (
        <section className="counselor-dashboard__queue" aria-label="Application queue">
          <table className="counselor-dashboard__table" data-testid="queue-table">
            <thead>
              <tr>
                <th scope="col">Student</th>
                <th scope="col">Email</th>
                <th scope="col">Phone</th>
                <th scope="col">Stage</th>
                <th scope="col">Added</th>
              </tr>
            </thead>
            <tbody>
              {applications.map((app) => (
                <tr key={app.id} data-testid={`queue-row-${app.id}`}>
                  <td className="counselor-dashboard__student-name">
                    {app.student_name ?? 'Unknown'}
                  </td>
                  <td>{app.student_email}</td>
                  <td>{app.student_phone ?? '-'}</td>
                  <td>
                    <span
                      className="counselor-dashboard__stage-tag"
                      style={{
                        '--badge-color': STAGE_COLORS[app.stage],
                      } as React.CSSProperties}
                      data-testid={`stage-tag-${app.id}`}
                    >
                      {STAGE_LABELS[app.stage]}
                    </span>
                  </td>
                  <td>{formatDate(app.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
