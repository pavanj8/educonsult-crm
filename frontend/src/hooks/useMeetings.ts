import { useCallback, useEffect, useState } from 'react'

import { scheduleMeeting } from '../api/meetings'
import { listMeetingsForApplication } from '../api/meetings'
import { isApiError } from '../api/client'
import type { Meeting, ScheduleMeetingRequest } from '../types/meeting'
import { hasAccessToken } from '../store/authStorage'

interface UseMeetingsResult {
  meetings: Meeting[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
}

/**
 * Hook for the counselor-side scheduling UI (E22; Journey J15;
 * frontend ticket #161). Loads the meetings that belong to a single
 * application via ``GET /applications/{id}/meetings`` and exposes a
 * small ``scheduleMeeting`` helper that drives the inline form on the
 * application row of the counselor dashboard.
 *
 * Defensive scoping:
 *  * Without an access token, returns an empty list (prevents a flash
 *    of 401 noise before the auth provider mounts).
 *  * 403 surfaces as a permission error (the role guard on the route
 *    should also have caught it -- but the staff user may have lost
 *    permission since login).
 *  * 401 surfaces as a sign-in reminder so the counselor knows to
 *    re-authenticate.
 *  * Network / unknown errors fall back to a generic message that does
 *    not leak the server response shape.
 */
export function useApplicationMeetings(applicationId: number): UseMeetingsResult {
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
      setMeetings(await listMeetingsForApplication(applicationId))
    } catch (err) {
      if (isApiError(err)) {
        if (err.status === 403) {
          setError('You do not have permission to view meetings for this application')
        } else if (err.status === 401) {
          setError('Sign in to view meetings for this application')
        } else if (err.status === 404) {
          setError('Application not found')
        } else {
          setError('Failed to load meetings for this application')
        }
      } else {
        setError('Failed to load meetings for this application')
      }
    } finally {
      setLoading(false)
    }
  }, [applicationId])

  useEffect(() => {
    void load()
  }, [load])

  return { meetings, loading, error, reload: load }
}

/** Result returned by {@link useScheduleMeeting}. */
interface UseScheduleMeetingResult {
  submitting: boolean
  /**
   * Schedule a meeting on the given application. Resolves to either
   * the freshly-created ``Meeting`` (success) or ``null`` (failure).
   * On failure, ``errorMessage`` carries the user-readable description
   * so the host can render it inline without reading React state.
   */
  schedule: (
    applicationId: number,
    payload: ScheduleMeetingRequest,
    onScheduled?: (meeting: Meeting) => void,
  ) => Promise<{ meeting: Meeting | null; errorMessage: string | null }>
  /**
   * Last error message for the most recent schedule call. Mirrors
   * ``errorMessage`` returned by the ``schedule`` call itself; the
   * stored snapshot is mainly for accessibility / stateful renders
   * that prefer to read React state instead of an awaited return.
   */
  submitError: string | null
}

/**
 * Schedule-meeting hook for the counselor UI (E22; Journey J15;
 * frontend ticket #161).
 *
 * ``schedule`` resolves to ``{ meeting, errorMessage }``. On success,
 * ``meeting`` is the created object and ``errorMessage`` is ``null``.
 * On failure, ``meeting`` is ``null`` and ``errorMessage`` carries a
 * user-readable description so the host can render it inline without
 * reading React state inside an async event handler.
 */
export function useScheduleMeeting(): UseScheduleMeetingResult {
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const schedule = useCallback(
    async (
      applicationId: number,
      payload: ScheduleMeetingRequest,
      onScheduled?: (meeting: Meeting) => void,
    ): Promise<{ meeting: Meeting | null; errorMessage: string | null }> => {
      setSubmitting(true)
      setSubmitError(null)
      try {
        const created = await scheduleMeeting(applicationId, payload)
        onScheduled?.(created)
        return { meeting: created, errorMessage: null }
      } catch (err) {
        const message = describeScheduleError(err)
        setSubmitError(message)
        return { meeting: null, errorMessage: message }
      } finally {
        setSubmitting(false)
      }
    },
    [],
  )

  return { submitting, submitError, schedule }
}

function describeScheduleError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to schedule meetings here"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) return err.message || 'Invalid meeting details'
  }
  return 'Failed to schedule the meeting'
}
