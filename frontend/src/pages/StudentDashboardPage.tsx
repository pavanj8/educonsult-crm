import { programName, universityName } from '../data/demoMasterData'
import { useApplications } from '../hooks/useApplications'
import { PIPELINE_STAGE_LABELS } from '../types/application'

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

export default function StudentDashboardPage() {
  const { applications, loading, error } = useApplications()

  return (
    <div className="student-dashboard" data-testid="student-dashboard-page">
      <header className="student-dashboard__header">
        <h2>Student dashboard</h2>
        <p className="student-dashboard__subtitle">
          View your university applications and track each pipeline stage.
        </p>
      </header>

      <section
        className="student-dashboard__section"
        aria-labelledby="applications-list-heading"
      >
        <h3 id="applications-list-heading">My applications</h3>
        {loading && <p className="student-dashboard__status">Loading applications…</p>}
        {error && (
          <p className="student-dashboard__status student-dashboard__status--error" role="alert">
            {error}
          </p>
        )}
        {!loading && !error && applications.length === 0 && (
          <p className="student-dashboard__status">No applications yet.</p>
        )}
        {!loading && !error && applications.length > 0 && (
          <div className="application-table-wrapper">
            <table className="application-table" data-testid="application-table">
              <thead>
                <tr>
                  <th scope="col">University</th>
                  <th scope="col">Program</th>
                  <th scope="col">Stage</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((application) => (
                  <tr key={application.id} data-testid={`application-row-${application.id}`}>
                    <td>{universityName(application.university_id)}</td>
                    <td>
                      {programName(application.university_id, application.program_id)}
                    </td>
                    <td>
                      <span
                        className="application-table__stage"
                        data-testid={`application-stage-${application.id}`}
                      >
                        {PIPELINE_STAGE_LABELS[application.stage]}
                      </span>
                    </td>
                    <td>{formatDate(application.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
