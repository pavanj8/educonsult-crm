import { useCallback, useState } from 'react'

import { isApiError } from '../api/client'
import { createStaff as createStaffApi } from '../api/staff'
import type { StaffCreateRequest } from '../types/staff'

export function useStaff() {
  const [createError, setCreateError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const createStaff = useCallback(async (payload: StaffCreateRequest) => {
    setSubmitting(true)
    setCreateError(null)
    try {
      const created = await createStaffApi(payload)
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

  return {
    createError,
    submitting,
    createStaff,
  }
}
