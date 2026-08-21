import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchAssignedApplications } from '../api/applications'
import { hasAccessToken } from '../store/authStorage'
import type { Application } from '../types/application'

/** Loads the staff member's assigned-application queue (E21; Journey J14). */
export function useAssignedApplications() {
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!hasAccessToken()) {
      setApplications([])
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setApplications(await fetchAssignedApplications())
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setError('You do not have permission to view assigned applications')
      } else if (isApiError(err) && err.status === 401) {
        setError('Sign in to view your assigned applications')
      } else {
        setError('Failed to load your assigned applications')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return { applications, loading, error, reload: load }
}
