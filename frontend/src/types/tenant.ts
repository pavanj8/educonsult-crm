/**
 * Tenant types aligned with backend E8 / E10 schemas.
 *
 * The ``logo_url``, ``brand_color``, and ``currency`` fields are owned
 * by the E10 tenant-branding workstream (#109 / #110 / #111) and are
 * returned by ``GET /tenants/{id}`` so the app shell (issue #113) can
 * theme the chrome with the tenant identity. ``currency`` is
 * guaranteed by the backend (NOT NULL column with a server default),
 * while the other two are nullable to represent "tenant has not yet
 * picked a brand color / uploaded a logo".
 */

export type Tenant = {
  id: number
  name: string
  slug: string
  logo_url: string | null
  /**
   * Canonical CSS hex form ``#RRGGBB`` (case insensitive on the wire;
   * the backend PATCH normalizer preserves the caller-supplied case).
   * Frontend callers should validate with ``parseHexColor`` from
   * ``store/brandingColor`` before passing the value to CSS.
   */
  brand_color: string | null
  /** ISO 4217 three-letter display currency code (E52). */
  currency: string
  created_at: string
  updated_at: string
}

export type TenantCreateRequest = {
  name: string
  slug: string
  owner_email: string
}

/**
 * Payload accepted by ``PATCH /tenants/{id}/branding`` (E10; Journey J3;
 * sibling backend ticket #110). Every field is optional — the backend applies
 * only the keys supplied — but the settings page always sends the full set so
 * any combination can change in one submit.
 */
export type TenantBrandingUpdateRequest = {
  logo_url?: string | null
  brand_color?: string | null
  currency?: string | null
}

/**
 * Curated ISO 4217 codes offered by the branding settings dropdown. The
 * backend (E10 / E52) accepts any valid ISO 4217 code; the frontend constrains
 * the dropdown to this set so the form is usable without listing every code.
 */
export const TENANT_BRANDING_CURRENCY_CODES = [
  'INR',
  'USD',
  'EUR',
  'GBP',
  'CAD',
  'AUD',
  'NZD',
  'SGD',
] as const

export type TenantBrandingCurrencyCode = (typeof TENANT_BRANDING_CURRENCY_CODES)[number]
