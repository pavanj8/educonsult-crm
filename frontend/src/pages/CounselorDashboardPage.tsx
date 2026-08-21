import { useAssignedApplications } from '../hooks/useAssignedApplications'
import { PIPELINE_STAGE_LABELS } from '../types/application'

function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString()
}

/**
 * Counselor dashboard — the signed-in staff member's assigned-application queue
 * (E21; Journey J14), with loading / error / empty states.
 */
export default function CounselorDashboardPage() {
  const { applications, loading, error, reload } = useAssignedApplications()

  return (
    <section className="counselor-dashboard" aria-labelledby="counselor-dashboard-heading">
      <header className="counselor-dashboard__header">
        <h1 id="counselor-dashboard-heading">My assigned applications</h1>
        <button type="button" onClick={() => void reload()} disabled={loading}>
          Refresh
        </button>
      </header>

      {loading ? (
        <p role="status" aria-live="polite" data-testid="counselor-queue-loading">
          Loading your applications…
        </p>
      ) : error ? (
        <p role="alert" data-testid="counselor-queue-error">
          {error}
        </p>
      ) : applications.length === 0 ? (
        <p data-testid="counselor-queue-empty">No applications are assigned to you.</p>
      ) : (
        <table className="counselor-queue-table" data-testid="counselor-queue-table">
          <caption className="sr-only">Applications assigned to you</caption>
          <thead>
            <tr>
              <th scope="col">Application</th>
              <th scope="col">Student</th>
              <th scope="col">University / Program</th>
              <th scope="col">Stage</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((app) => (
              <tr key={app.id} data-testid={`counselor-queue-row-${app.id}`}>
                <td>#{app.id}</td>
                <td>#{app.student_id}</td>
                <td>
                  #{app.university_id} / #{app.program_id}
                </td>
                <td>{PIPELINE_STAGE_LABELS[app.stage]}</td>
                <td>{formatDate(app.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
