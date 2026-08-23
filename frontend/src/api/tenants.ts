import { apiFetch } from './client'
import type {
  Tenant,
  TenantBrandingUpdateRequest,
  TenantCreateRequest,
} from '../types/tenant'

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

/**
 * Update a tenant's branding (logo URL, brand color, currency) via
 * ``PATCH /tenants/{id}/branding`` (E10; Journey J3; sibling backend ticket
 * #110). The backend applies only the fields supplied; the settings page
 * always sends the full editable set. The returned :class:`Tenant` reflects
 * the server's normalised form (canonical hex color, upper-cased ISO 4217
 * currency) and is what the caller re-renders with.
 */
export async function updateTenantBranding(
  tenantId: number,
  payload: TenantBrandingUpdateRequest,
): Promise<Tenant> {
  return apiFetch<Tenant>(`/tenants/${tenantId}/branding`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

/**
 * Upload a new tenant logo via ``POST /tenants/{id}/logo`` (E10; Journey J3;
 * sibling backend ticket #111). Sent as multipart/form-data — ``skipContentType``
 * lets the browser set the multipart boundary. Bearer-token auth (not cookies)
 * means this is not CSRF-exposed. Returns the updated :class:`Tenant`.
 */
export async function uploadTenantLogo(tenantId: number, file: File): Promise<Tenant> {
  const formData = new FormData()
  formData.append('file', file)

  return apiFetch<Tenant>(`/tenants/${tenantId}/logo`, {
    method: 'POST',
    body: formData,
    skipContentType: true,
  })
}
