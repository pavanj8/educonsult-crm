import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import {
  createBranch as createBranchApi,
  fetchBranches,
  updateBranch as updateBranchApi,
} from '../api/branches'
import type { Branch, BranchCreateRequest, BranchUpdateRequest } from '../types/branch'

import { hasAccessToken } from '../store/authStorage'

export function useBranches() {
  const [branches, setBranches] = useState<Branch[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [updateError, setUpdateError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

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

  const createBranch = useCallback(async (payload: BranchCreateRequest) => {
    setSubmitting(true)
    setCreateError(null)
    try {
      const created = await createBranchApi(payload)
      setBranches((prev) => [...prev, created])
      return created
    } catch (err) {
      if (isApiError(err)) {
        setCreateError(err.message)
      } else {
        setCreateError('Failed to create branch')
      }
      throw err
    } finally {
      setSubmitting(false)
    }
  }, [])

  const updateBranch = useCallback(async (id: number, payload: BranchUpdateRequest) => {
    setSubmitting(true)
    setUpdateError(null)
    try {
      const updated = await updateBranchApi(id, payload)
      setBranches((prev) => prev.map((branch) => (branch.id === id ? updated : branch)))
      return updated
    } catch (err) {
      if (isApiError(err)) {
        setUpdateError(err.message)
      } else {
        setUpdateError('Failed to update branch')
      }
      throw err
    } finally {
      setSubmitting(false)
    }
  }, [])

  return {
    branches,
    loading,
    error,
    createError,
    updateError,
    submitting,
    reload: loadBranches,
    createBranch,
    updateBranch,
  }
}
