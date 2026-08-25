/**
 * Custom hook for fetching all tenants' billing status (E47; Journey J40).
 */

import { useEffect, useState } from 'react'

import { fetchAllTenantsBillingStatus } from '../api/plans'
import type { TenantBillingStatus } from '../types/plan'

interface UseAllTenantsBillingStatusState {
  tenants: TenantBillingStatus[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
}

/**
 * Hook to fetch all tenants' billing/subscription status.
 *
 * This hook calls the backend endpoint GET /billing/tenant-status on mount
 * and provides a list of all tenants with their assigned plan details
 * and current usage counts (branches, staff, students).
 *
 * The hook handles loading, error, and retry states automatically.
 * Callers can use `reload()` to refresh the data.
 *
 * This hook is intended for super admin use only; other roles will receive
 * a 403 error from the backend.
 */
export function useAllTenantsBillingStatus(): UseAllTenantsBillingStatusState {
  const [state, setState] = useState<{
    tenants: TenantBillingStatus[]
    loading: boolean
    error: string | null
  }>({
    tenants: [],
    loading: true,
    error: null,
  })

  const fetch = async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const data = await fetchAllTenantsBillingStatus()
      setState({ tenants: data, loading: false, error: null })
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load tenant billing status'
      setState({ tenants: [], loading: false, error: message })
    }
  }

  // Fetch on mount
  useEffect(() => {
    void fetch()
  }, [])

  const reload = async () => {
    await fetch()
  }

  return { ...state, reload }
}
