import { useCallback, useState } from 'react'

import { isApiError } from '../api/client'
import { createApplication as createApplicationApi } from '../api/applications'
import type { CreateApplicationRequest } from '../types/application'

export function useCreateApplication() {
  const [submitting, setSubmitting] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const createApplication = useCallback(async (payload: CreateApplicationRequest) => {
    setSubmitting(true)
    setCreateError(null)
    try {
      return await createApplicationApi(payload)
    } catch (err) {
      if (isApiError(err)) {
        setCreateError(err.message)
      } else {
        setCreateError('Failed to create application')
      }
      throw err
    } finally {
      setSubmitting(false)
    }
  }, [])

  return {
    submitting,
    createError,
    createApplication,
  }
}