import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchTenant } from '../api/tenants'
import type { Tenant } from '../types/tenant'

import { useAuth } from '../store/authStore'

/**
 * Tenant branding hook (E10; Journey J3; issue #113).
 *
 * Reads the authenticated user's tenant profile — name, logo, brand
 * color, currency — and exposes a normalized ``Tenant`` record so the
 * app shell (and, in #112, the branding settings page) can theme the
 * chrome with the tenant's identity.
 *
 * Data source
 * -----------
 * Calls ``GET /tenants/{id}`` where ``id`` is ``current_user.tenant_id``
 * from ``/auth/me``. ``TENANT_READ`` is granted only to
 * ``SUPER_ADMIN`` today, so this hook returns ``null`` for other roles
 * (the shell renders its default chrome in that case — the design is
 * documented in the ticket so a future, owner-side read endpoint is a
 * drop-in change here).
 *
 * Behavior
 * --------
 * * On mount and whenever the authenticated ``tenant_id`` changes, the
 *   hook issues one fetch.
 * * Permission errors (403/401) are swallowed silently — the app shell
 *   just keeps its default theme. A genuine 404 (tenant row absent)
 *   also surfaces as ``null`` rather than crashing the shell.
 * * Other errors (transient network / 5xx) are exposed as ``error``
 *   so callers can decide to show a non-blocking toast in future;
 *   today's shell render path ignores ``error`` and falls back to the
 *   default theme.
 *
 * The hook is intentionally synchronous from the perspective of any
 * caller that treats ``null`` as "no theme yet" — no caller needs to
 * ``await`` it. The CSS-variable side-effect is applied by the
 * :mod:`brandingStore` consumer that wraps this hook.
 */
export function useTenantBranding() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id ?? null

  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState<boolean>(tenantId !== null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (id: number) => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchTenant(id)
      setTenant(data)
    } catch (err) {
      if (isApiError(err)) {
        // Permission (401/403), not-found, or "tenant doesn't belong
        // to this user" — all are non-fatal for the app shell. They
        // mean "no theme available" rather than a real error to
        // surface.
        if (err.status === 401 || err.status === 403 || err.status === 404) {
          setTenant(null)
        } else {
          setError(err.message)
          setTenant(null)
        }
      } else {
        setError('Failed to load tenant branding')
        setTenant(null)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tenantId === null) {
      setTenant(null)
      setLoading(false)
      setError(null)
      return
    }
    void load(tenantId)
  }, [tenantId, load])

  const reload = useCallback(async () => {
    if (tenantId === null) {
      return
    }
    await load(tenantId)
  }, [tenantId, load])

  return { tenant, loading, error, reload }
}
