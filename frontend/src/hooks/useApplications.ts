import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchApplications } from '../api/applications'
import type { Application } from '../types/application'

import { hasAccessToken } from '../store/authStorage'

export function useApplications() {
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadApplications = useCallback(async () => {
    if (!hasAccessToken()) {
      setApplications([])
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await fetchApplications()
      setApplications(data)
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setError('You do not have permission to view applications')
      } else if (isApiError(err) && err.status === 401) {
        setError('Sign in to view applications')
      } else {
        setError('Failed to load applications')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadApplications()
  }, [loadApplications])

  return {
    applications,
    loading,
    error,
    reload: loadApplications,
  }
}
