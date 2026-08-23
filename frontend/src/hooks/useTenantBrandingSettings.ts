import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import {
  fetchTenant,
  updateTenantBranding,
  uploadTenantLogo,
} from '../api/tenants'
import type { Tenant, TenantBrandingUpdateRequest } from '../types/tenant'

/**
 * Single source of truth for the "no tenant is associated with the current
 * account" message. Both ``updateBranding`` and ``uploadLogo`` surface this
 * verbatim via their rejection (so callers can ``await`` and observe it)
 * AND set it on the relevant error state slot (so the page renders it
 * inline). Extracting the literal at module scope keeps the two surfaces
 * in lock-step if the wording ever changes.
 */
const NO_TENANT_MESSAGE = 'No tenant is associated with the current account'

/**
 * State and actions for the tenant branding settings page (E10; Journey J3;
 * sibling frontend ticket #112).
 *
 * The hook owns all loading / error state so the page only has to manage
 * local form state:
 *
 * * ``tenant`` -- the most recently fetched/branding/saved :class:`Tenant`,
 *   or ``null`` while the initial GET has not completed. The page MUST NOT
 *   let the user submit ``updateBranding`` / ``uploadLogo`` until the
 *   initial ``tenantId`` GET has either succeeded (so the form is hydrated
 *   with existing values) or failed (so we know the page cannot safely
 *   clobber the row).
 * * ``loadingTenant`` -- ``true`` while the initial ``GET /tenants/{id}`` is
 *   in flight.
 * * ``loadError`` -- non-null if the initial load failed; the page renders
 *   this as an inline error and disables submit so the user cannot save
 *   over data they never saw.
 * * ``brandingError`` / ``logoError`` -- last error from each write path,
 *   cleared automatically when a new request starts.
 *
 * The page treats ``tenant !== null && !loadingTenant`` as the "form is
 * hydrated" gate and only enables submit / upload in that state.
 */
export function useTenantBrandingSettings(tenantId: number | null) {
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loadingTenant, setLoadingTenant] = useState<boolean>(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [brandingError, setBrandingError] = useState<string | null>(null)
  const [logoError, setLogoError] = useState<string | null>(null)
  const [submittingBranding, setSubmittingBranding] = useState(false)
  const [submittingLogo, setSubmittingLogo] = useState(false)

  const loadTenant = useCallback(async (): Promise<void> => {
    if (tenantId === null) {
      setTenant(null)
      setLoadError(null)
      setLoadingTenant(false)
      return
    }

    setLoadingTenant(true)
    setLoadError(null)
    try {
      const fetched = await fetchTenant(tenantId)
      setTenant(fetched)
    } catch (err) {
      if (isApiError(err)) {
        setLoadError(err.message)
      } else {
        setLoadError('Failed to load tenant branding settings')
      }
    } finally {
      setLoadingTenant(false)
    }
  }, [tenantId])

  useEffect(() => {
    void loadTenant()
  }, [loadTenant])

  const updateBranding = useCallback(
    async (payload: TenantBrandingUpdateRequest): Promise<Tenant> => {
      if (tenantId === null) {
        // Record the no-tenant error on the error slot, then reject so the
        // caller can `await` it. The page catches the rejection and renders
        // ``brandingError`` inline.
        setBrandingError(NO_TENANT_MESSAGE)
        throw new Error(NO_TENANT_MESSAGE)
      }

      setSubmittingBranding(true)
      setBrandingError(null)
      try {
        const updated = await updateTenantBranding(tenantId, payload)
        setTenant(updated)
        return updated
      } catch (err) {
        if (isApiError(err)) {
          setBrandingError(err.message)
        } else {
          setBrandingError('Failed to save branding settings')
        }
        throw err
      } finally {
        setSubmittingBranding(false)
      }
    },
    [tenantId],
  )

  const uploadLogo = useCallback(
    async (file: File): Promise<Tenant> => {
      if (tenantId === null) {
        // See updateBranding: record the error, then reject for the caller.
        setLogoError(NO_TENANT_MESSAGE)
        throw new Error(NO_TENANT_MESSAGE)
      }

      setSubmittingLogo(true)
      setLogoError(null)
      try {
        const updated = await uploadTenantLogo(tenantId, file)
        setTenant(updated)
        return updated
      } catch (err) {
        if (isApiError(err)) {
          setLogoError(err.message)
        } else {
          setLogoError('Failed to upload logo')
        }
        throw err
      } finally {
        setSubmittingLogo(false)
      }
    },
    [tenantId],
  )

  const clearBrandingError = useCallback(() => setBrandingError(null), [])
  const clearLogoError = useCallback(() => setLogoError(null), [])

  return {
    tenant,
    loadingTenant,
    loadError,
    brandingError,
    logoError,
    submittingBranding,
    submittingLogo,
    updateBranding,
    uploadLogo,
    reload: loadTenant,
    clearBrandingError,
    clearLogoError,
  }
}
