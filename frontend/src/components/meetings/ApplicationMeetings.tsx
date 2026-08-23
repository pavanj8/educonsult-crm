import { useState } from 'react'

import MeetingsList from './MeetingsList'
import ScheduleMeetingAction from './ScheduleMeetingAction'

interface ApplicationMeetingsProps {
  applicationId: number
  /**
   * When ``true`` the schedule form is hidden (read-only mode). Used when
   * the signed-in user lacks the ``meeting:schedule`` permission -- the
   * existing meetings list is still shown, but no new-meeting button
   * appears. Defaults to ``false``.
   */
  readOnly?: boolean
}

/**
 * Per-application meetings widget bundled for the counselor queue (E22;
 * Journey J15; frontend ticket #161). Composes the existing list with
 * the schedule form behind a single "Schedule a meeting" disclosure so
 * each application row of the counselor dashboard carries one tidy
 * surface rather than three siblings.
 */
export default function ApplicationMeetings({
  applicationId,
  readOnly = false,
}: ApplicationMeetingsProps) {
  const [scheduleCounter, setScheduleCounter] = useState(0)
  // ``scheduleCounter`` is incremented whenever a meeting is scheduled
  // or the meetings list reloads, forcing the MeetingsList child to
  // re-mount its internal state. Avoids having to build a share-cache
  // for the (very small) list -- the per-application meetings table is
  // cheap to rebuild and is only a few rows in practice.
  const bumpCounter = () => setScheduleCounter((value) => value + 1)

  return (
    <section
      aria-labelledby={`application-meetings-heading-${applicationId}`}
      className="application-meetings"
      data-testid={`application-meetings-${applicationId}`}
    >
      <h3 id={`application-meetings-heading-${applicationId}`}>Meetings</h3>
      <MeetingsList applicationId={applicationId} onChanged={bumpCounter} key={scheduleCounter} />
      <ScheduleMeetingAction applicationId={applicationId} onScheduled={bumpCounter} readOnly={readOnly} />
    </section>
  )
}
