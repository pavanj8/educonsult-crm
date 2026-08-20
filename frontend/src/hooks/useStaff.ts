import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import {
  createStaff as createStaffApi,
  deactivateStaff as deactivateStaffApi,
  fetchStaff,
  fetchStaffById,
  reactivateStaff as reactivateStaffApi,
  updateStaff as updateStaffApi,
} from '../api/staff'
import type { Staff, StaffCreateRequest, StaffUpdateRequest } from '../types/staff'

import { hasAccessToken } from '../store/authStorage'

export function useStaff() {
  const [staff, setStaff] = useState<Staff[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [updateError, setUpdateError] = useState<string | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [togglingId, setTogglingId] = useState<number | null>(null)

  const loadStaff = useCallback(async () => {
    if (!hasAccessToken()) {
      setStaff([])
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await fetchStaff()
      setStaff(data)
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setError('You do not have permission to view staff')
      } else if (isApiError(err) && err.status === 401) {
        setError('Sign in to view staff')
      } else {
        setError('Failed to load staff')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadStaff()
  }, [loadStaff])

  const loadStaffMember = useCallback(async (id: number) => {
    return fetchStaffById(id)
  }, [])

  const createStaff = useCallback(async (payload: StaffCreateRequest) => {
    setSubmitting(true)
    setCreateError(null)
    try {
      const created = await createStaffApi(payload)
      setStaff((prev) => [...prev, created])
      return created
    } catch (err) {
      if (isApiError(err)) {
        setCreateError(err.message)
      } else {
        setCreateError('Failed to create staff account')
      }
      throw err
    } finally {
      setSubmitting(false)
    }
  }, [])

  const updateStaff = useCallback(async (id: number, payload: StaffUpdateRequest) => {
    setSubmitting(true)
    setUpdateError(null)
    try {
      const updated = await updateStaffApi(id, payload)
      setStaff((prev) => prev.map((member) => (member.id === id ? updated : member)))
      return updated
    } catch (err) {
      if (isApiError(err)) {
        setUpdateError(err.message)
      } else {
        setUpdateError('Failed to update staff account')
      }
      throw err
    } finally {
      setSubmitting(false)
    }
  }, [])

  const setStaffActiveStatus = useCallback(async (id: number, active: boolean) => {
    setTogglingId(id)
    setStatusError(null)
    try {
      const updated = active ? await reactivateStaffApi(id) : await deactivateStaffApi(id)
      setStaff((prev) => prev.map((member) => (member.id === id ? updated : member)))
      return updated
    } catch (err) {
      if (isApiError(err)) {
        setStatusError(err.message)
      } else {
        setStatusError(active ? 'Failed to reactivate staff account' : 'Failed to deactivate staff account')
      }
      throw err
    } finally {
      setTogglingId(null)
    }
  }, [])

  return {
    staff,
    loading,
    error,
    createError,
    updateError,
    statusError,
    submitting,
    togglingId,
    reload: loadStaff,
    loadStaffMember,
    createStaff,
    updateStaff,
    setStaffActiveStatus,
  }
}
