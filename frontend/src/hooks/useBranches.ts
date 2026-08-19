import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchBranches } from '../api/branches'
import type { Branch } from '../types/branch'

import { hasAccessToken } from '../store/authStorage'

export function useBranches() {
  const [branches, setBranches] = useState<Branch[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadBranches = useCallback(async () => {
    if (!hasAccessToken()) {
      setBranches([])
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await fetchBranches()
      setBranches(data)
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setError('You do not have permission to view branches')
      } else if (isApiError(err) && err.status === 401) {
        setError('Sign in to view branches')
      } else {
        setError('Failed to load branches')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadBranches()
  }, [loadBranches])

  return {
    branches,
    loading,
    error,
    reload: loadBranches,
  }
}
