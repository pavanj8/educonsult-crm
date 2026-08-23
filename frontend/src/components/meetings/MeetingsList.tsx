import { useApplicationMeetings } from '../../hooks/useMeetings'

interface MeetingsListProps {
  applicationId: number
  /** Called after a meeting is scheduled / updated so the list reloads. */
  onChanged?: (applicationId: number) => void
}

/**
 * The list of meetings already scheduled for a given application
 * (E22; Journey J15; frontend ticket #161). Backed by
 * ``GET /applications/{id}/meetings`` (ticket #160). Renders a small
 * "Upcoming meetings" widget under each row of the counselor queue so
 * the counselor can see at a glance what's already on the calendar for
 * a student / application.
 *
 * The widget treats the empty state ("no meetings yet") as a normal,
 * user-friendly message rather than as an error -- a brand-new
 * application commonly has zero scheduled meetings until the counselor
 * chooses a slot.
 */
export default function MeetingsList({
  applicationId,
  onChanged,
}: MeetingsListProps) {
  const { meetings, loading, error, reload } = useApplicationMeetings(applicationId)

  function handleReload() {
    void reload().then(() => onChanged?.(applicationId))
  }

  if (loading) {
    return (
      <p
        role="status"
        aria-live="polite"
        data-testid={`meetings-loading-${applicationId}`}
      >
        Loading meetings…
      </p>
    )
  }

  if (error) {
    return (
      <p role="alert" data-testid={`meetings-error-${applicationId}`}>
        {error}
      </p>
    )
  }

  if (meetings.length === 0) {
    return (
      <p data-testid={`meetings-empty-${applicationId}`}>No meetings scheduled yet.</p>
    )
  }

  return (
    <div className="meetings-list" data-testid={`meetings-list-${applicationId}`}>
      <table aria-label="Scheduled meetings">
        <caption className="sr-only">Scheduled meetings for this application</caption>
        <thead>
          <tr>
            <th scope="col">When</th>
            <th scope="col">Duration</th>
            <th scope="col">Location</th>
            <th scope="col">Notes</th>
          </tr>
        </thead>
        <tbody>
          {meetings.map((meeting) => (
            <tr key={meeting.id} data-testid={`meeting-row-${meeting.id}`}>
              <td>{formatDateTime(meeting.scheduled_at)}</td>
              <td>{meeting.duration_minutes} min</td>
              <td>{meeting.location ?? '—'}</td>
              <td>{meeting.notes ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        type="button"
        onClick={handleReload}
        data-testid={`meetings-reload-${applicationId}`}
      >
        Refresh meetings
      </button>
    </div>
  )
}

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}
