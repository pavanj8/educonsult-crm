import { useCallback, useState } from 'react'

import { isApiError } from '../api/client'
import { createApplication as createApplicationApi } from '../api/applications'
import type { Application, CreateApplicationRequest } from '../types/application'

export function useCreateApplication() {
  const [submitting, setSubmitting] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [lastCreated, setLastCreated] = useState<Application | null>(null)

  const createApplication = useCallback(async (payload: CreateApplicationRequest) => {
    setSubmitting(true)
    setCreateError(null)
    try {
      const created = await createApplicationApi(payload)
      setLastCreated(created)
      return created
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

  const clearLastCreated = useCallback(() => {
    setLastCreated(null)
  }, [])

  return {
    submitting,
    createError,
    lastCreated,
    createApplication,
    clearLastCreated,
  }
}
