import { useCallback, useEffect, useMemo, useState } from 'react'

import { listMyMeetings } from '../api/meetings'
import { isApiError } from '../api/client'
import type { Meeting } from '../types/meeting'
import { hasAccessToken } from '../store/authStorage'

interface UseStudentUpcomingMeetingsResult {
  /** Meetings with ``scheduled_at >= now``, soonest first. */
  upcoming: Meeting[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
}

/**
 * Student-side hook for E23 (Journey J16; frontend ticket #162).
 *
 * Loads all meetings that belong to the authenticated student via
 * ``GET /me/meetings`` and surfaces only the future ones (the widget
 * is specifically for "upcoming meetings" -- past meetings are not
 * shown). The backend is expected to scope the query to the
 * authenticated student's ``student_id``; the client filters by
 * ``scheduled_at`` defensively in case the server returns the full
 * history (cheaper than guessing the server's exact filter contract).
 *
 * Defensive scoping:
 *  * Without an access token, returns an empty list (prevents a flash
 *    of 401 noise before the auth provider mounts).
 *  * 403 surfaces as a permission error (the StudentRoute guard should
 *    also have caught it -- but the student may have lost the role
 *    since login).
 *  * 401 surfaces as a sign-in reminder.
 *  * Other errors fall back to a generic message that does not leak
 *    the server response shape.
 */
export function useStudentUpcomingMeetings(): UseStudentUpcomingMeetingsResult {
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!hasAccessToken()) {
      setMeetings([])
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const all = await listMyMeetings()
      setMeetings(all)
    } catch (err) {
      if (isApiError(err)) {
        if (err.status === 403) {
          setError('You do not have permission to view your meetings')
        } else if (err.status === 401) {
          setError('Sign in to view your meetings')
        } else {
          setError('Failed to load your upcoming meetings')
        }
      } else {
        setError('Failed to load your upcoming meetings')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const upcoming = useMemo(() => {
    const now = Date.now()
    return meetings
      .filter((meeting) => {
        const time = new Date(meeting.scheduled_at).getTime()
        return !Number.isNaN(time) && time >= now
      })
      .slice()
      .sort((a, b) => {
        const aTime = new Date(a.scheduled_at).getTime()
        const bTime = new Date(b.scheduled_at).getTime()
        return aTime - bTime
      })
  }, [meetings])

  return { upcoming, loading, error, reload: load }
}