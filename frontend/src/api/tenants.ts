import { apiFetch } from './client'
import type { Tenant, TenantCreateRequest } from '../types/tenant'

export async function fetchTenants(): Promise<Tenant[]> {
  return apiFetch<Tenant[]>('/tenants')
}

/**
 * Fetch a single tenant record by id.
 *
 * Endpoint: ``GET /tenants/{id}`` (E8; Journey J1; E10 branding read path).
 *
 * The endpoint surfaces the tenant's branding columns —
 * ``logo_url`` / ``brand_color`` / ``currency`` — that the E10
 * frontend theming task (#113) reads to theme the app shell. The
 * backend currently grants ``TENANT_READ`` only to ``SUPER_ADMIN``,
 * so this client will surface a 403 for consultancy owners and other
 * roles; callers (e.g. :func:`useTenantBranding`) handle that error
 * by skipping theming rather than failing the render.
 */
export async function fetchTenant(tenantId: number): Promise<Tenant> {
  return apiFetch<Tenant>(`/tenants/${tenantId}`)
}

export async function createTenant(payload: TenantCreateRequest): Promise<Tenant> {
  return apiFetch<Tenant>('/tenants', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
