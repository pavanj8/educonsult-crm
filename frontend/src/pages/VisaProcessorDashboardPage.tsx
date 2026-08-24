import { useVisaQueue } from '../hooks/useVisaQueue'
import { PIPELINE_STAGE_LABELS } from '../types/application'

function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString()
}

/**
 * Visa processor dashboard — the visa-stage applications queue view
 * (E33; Journey J26; #192). Lists applications currently in the
 * ``visa_processing`` pipeline stage so the visa processor can pick
 * the next application to work on. Visa detail recording (E34) and
 * outcome updates (E35) are out of scope for this ticket; the rows
 * here are intentionally read-only.
 */
export default function VisaProcessorDashboardPage() {
  const { applications, total, loading, error, reload } = useVisaQueue()

  return (
    <section
      className="visa-processor-dashboard"
      aria-labelledby="visa-processor-dashboard-heading"
    >
      <header className="visa-processor-dashboard__header">
        <h1 id="visa-processor-dashboard-heading">Visa queue</h1>
        <button type="button" onClick={() => void reload()} disabled={loading}>
          Refresh
        </button>
      </header>

      {/*
        The live region intentionally wraps the entire dashboard body
        so that toggling aria-busy to true while a refetch is in flight
        is announced by screen readers regardless of which subtree
        (table vs. error vs. empty) is currently visible. This is the
        same "busy container" pattern used by the document-verifier
        dashboard.
      */}
      <div
        role="region"
        aria-live="polite"
        aria-busy={loading}
        data-testid="visa-queue-region"
      >
        {loading ? (
          <p role="status" aria-live="polite" data-testid="visa-queue-loading">
            Loading visa applications…
          </p>
        ) : error ? (
          <p role="alert" data-testid="visa-queue-error">
            {error}
          </p>
        ) : applications.length === 0 ? (
          <p data-testid="visa-queue-empty">No applications are at the visa stage.</p>
        ) : (
          <>
            <p data-testid="visa-queue-count">
              {total} application{total === 1 ? '' : 's'} at the visa stage
            </p>
            <table className="visa-queue-table" data-testid="visa-queue-table">
              <caption className="sr-only">Applications at the visa stage</caption>
              <thead>
                <tr>
                  <th scope="col">Application</th>
                  <th scope="col">Student</th>
                  <th scope="col">Branch</th>
                  <th scope="col">Counselor</th>
                  <th scope="col">University / Program</th>
                  <th scope="col">Stage</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr key={app.id} data-testid={`visa-queue-row-${app.id}`}>
                    <td>#{app.id}</td>
                    <td>#{app.student_id}</td>
                    <td>{app.branch_id == null ? '—' : `#${app.branch_id}`}</td>
                    <td>
                      {app.assigned_counselor_id == null
                        ? '—'
                        : `#${app.assigned_counselor_id}`}
                    </td>
                    <td>
                      #{app.university_id} / #{app.program_id}
                    </td>
                    <td>
                      {PIPELINE_STAGE_LABELS[app.stage as keyof typeof PIPELINE_STAGE_LABELS] ??
                        app.stage}
                    </td>
                    <td>{formatDate(app.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </section>
  )
}
