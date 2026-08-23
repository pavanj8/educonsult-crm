import { useId } from 'react'

import { useStudentUpcomingMeetings } from '../../hooks/useStudentUpcomingMeetings'

/**
 * Student-side "Upcoming meetings" widget (E23; Journey J16; frontend
 * ticket #162). Renders on the student dashboard above the new
 * application form. Backed by ``GET /me/meetings`` -- the backend
 * scopes the result to the authenticated student's ``student_id``.
 *
 * The widget is read-only (the student cannot schedule meetings --
 * scheduling is the counselor's job per J15 / E22). It only surfaces
 * future meetings (``scheduled_at >= now``); past meetings are not
 * shown. The empty / loading / error states follow the same
 * accessibility conventions as the rest of the student dashboard.
 */
export default function UpcomingMeetings() {
  const { upcoming, loading, error, reload } = useStudentUpcomingMeetings()
  const headingId = useId()

  return (
    <section
      className="upcoming-meetings"
      aria-labelledby={headingId}
      data-testid="upcoming-meetings-widget"
    >
      <div className="upcoming-meetings__header">
        <h3 id={headingId}>Upcoming meetings</h3>
        <button
          type="button"
          className="upcoming-meetings__reload"
          data-testid="upcoming-meetings-reload"
          onClick={() => {
            void reload()
          }}
        >
          Refresh
        </button>
      </div>

      {loading && (
        <p
          className="upcoming-meetings__status"
          role="status"
          aria-live="polite"
          data-testid="upcoming-meetings-loading"
        >
          Loading your upcoming meetings…
        </p>
      )}

      {!loading && error && (
        <p
          className="upcoming-meetings__status upcoming-meetings__status--error"
          role="alert"
          data-testid="upcoming-meetings-error"
        >
          {error}
        </p>
      )}

      {!loading && !error && upcoming.length === 0 && (
        <p
          className="upcoming-meetings__status"
          data-testid="upcoming-meetings-empty"
        >
          You have no upcoming meetings. Your counselor will let you know once
          one is scheduled.
        </p>
      )}

      {!loading && !error && upcoming.length > 0 && (
        <ul
          className="upcoming-meetings__list"
          data-testid="upcoming-meetings-list"
          aria-label="Upcoming meetings"
        >
          {upcoming.map((meeting) => (
            <li
              key={meeting.id}
              className="upcoming-meetings__item"
              data-testid={`upcoming-meeting-${meeting.id}`}
            >
              <div className="upcoming-meetings__when">
                {formatDate(meeting.scheduled_at)} at {formatTime(meeting.scheduled_at)}
              </div>
              <div className="upcoming-meetings__duration">
                {meeting.duration_minutes} min
              </div>
              {meeting.location ? (
                <div className="upcoming-meetings__location">
                  <span className="upcoming-meetings__label">Location: </span>
                  {meeting.location}
                </div>
              ) : null}
              {meeting.notes ? (
                <div className="upcoming-meetings__notes">
                  <span className="upcoming-meetings__label">Notes: </span>
                  {meeting.notes}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function formatTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
}