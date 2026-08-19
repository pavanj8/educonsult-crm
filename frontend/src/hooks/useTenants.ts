import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { createTenant as createTenantApi, fetchTenants } from '../api/tenants'
import type { Tenant, TenantCreateRequest } from '../types/tenant'

import { hasAccessToken } from '../store/authStorage'

export function useTenants() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const loadTenants = useCallback(async () => {
    if (!hasAccessToken()) {
      setTenants([])
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await fetchTenants()
      setTenants(data)
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setError('You do not have permission to view tenants')
      } else if (isApiError(err) && (err.status === 401 || err.status === 403)) {
        setError('Sign in to view tenants')
      } else {
        setError('Failed to load tenants')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadTenants()
  }, [loadTenants])

  const createTenant = useCallback(
    async (payload: TenantCreateRequest) => {
      setSubmitting(true)
      setCreateError(null)
      try {
        const created = await createTenantApi(payload)
        setTenants((prev) => [...prev, created])
        return created
      } catch (err) {
        if (isApiError(err)) {
          setCreateError(err.message)
        } else {
          setCreateError('Failed to create tenant')
        }
        throw err
      } finally {
        setSubmitting(false)
      }
    },
    [],
  )

  return {
    tenants,
    loading,
    error,
    createError,
    submitting,
    reload: loadTenants,
    createTenant,
  }
}
