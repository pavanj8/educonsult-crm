import { useId } from 'react'

import ApplicationMeetings from '../components/meetings/ApplicationMeetings'
import ApplicationNotes from '../components/notes/ApplicationNotes'
import { useAssignedApplications } from '../hooks/useAssignedApplications'
import { PIPELINE_STAGE_LABELS } from '../types/application'
import { useAuth } from '../store/authStore'

function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString()
}

/**
 * Counselor dashboard — the signed-in staff member's assigned-application queue
 * (E21; Journey J14), with loading / error / empty states. Each row carries
 * the E22 meetings widget (Journey J15, frontend ticket #161) so the
 * counselor can review already-scheduled meetings and schedule new ones
 * against the same application without leaving the queue, and the E24
 * notes thread (Journey J17, frontend ticket #166) so counselors can
 * read and author internal counseling notes anchored to the
 * application without leaving the queue either.
 */
export default function CounselorDashboardPage() {
  const { applications, loading, error, reload } = useAssignedApplications()
  const { user } = useAuth()
  const currentUserId = user?.id ?? null

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
              <th scope="col">Meetings</th>
              <th scope="col">Notes</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((app) => (
              <CounselorQueueRow
                key={app.id}
                applicationId={app.id}
                studentId={app.student_id}
                universityId={app.university_id}
                programId={app.program_id}
                stage={app.stage}
                createdAt={app.created_at}
                currentUserId={currentUserId}
              />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

interface CounselorQueueRowProps {
  applicationId: number
  studentId: number
  universityId: number
  programId: number
  stage: string
  createdAt: string
  currentUserId: number | null
}

function CounselorQueueRow({
  applicationId,
  studentId,
  universityId,
  programId,
  stage,
  createdAt,
  currentUserId,
}: CounselorQueueRowProps) {
  // A stable, row-scoped id prefix avoids collisions across rows and
  // makes the schedule form's aria-labelledby pair with the heading.
  const rowKey = useId()
  const headingId = `counselor-queue-row-${applicationId}-heading-${rowKey}`
  return (
    <tr data-testid={`counselor-queue-row-${applicationId}`}>
      <th scope="row" id={headingId}>
        #{applicationId}
      </th>
      <td>#{studentId}</td>
      <td>
        #{universityId} / #{programId}
      </td>
      <td>{PIPELINE_STAGE_LABELS[stage as keyof typeof PIPELINE_STAGE_LABELS] ?? stage}</td>
      <td>{formatDate(createdAt)}</td>
      <td>
        <ApplicationMeetings applicationId={applicationId} />
      </td>
      <td>
        <ApplicationNotes
          applicationId={applicationId}
          studentId={studentId}
          currentUserId={currentUserId}
        />
      </td>
    </tr>
  )
}
