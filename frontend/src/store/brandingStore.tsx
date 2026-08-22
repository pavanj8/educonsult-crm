import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react'

import { useTenantBranding } from '../hooks/useTenantBranding'

/**
 * Hex color string in ``#RRGGBB`` form (E10 / J3 brand color contract:
 * the backend's ``tenants.brand_color`` column carries the same canonical
 * 7-char shape). The frontend accepts both 6-digit (``#abc123``) and
 * 7-digit forms because the backend ships the value verbatim. CSS
 * variables are always written as the supplied value; the contrast
 * variable below normalizes to ``#ffffff`` for picking readable text on
 * top of the brand color.
 */
type BrandColor = `#${string}`

type BrandingContextValue = {
  /** Tenant id used to load branding — null when unauthenticated. */
  tenantId: number | null
  /** Tenant display name (e.g. for the header tagline). */
  tenantName: string | null
  /** Tenant slug (e.g. for footer / copy). */
  tenantSlug: string | null
  /** Absolute https URL of the tenant logo, or null if not set. */
  logoUrl: string | null
  /**
   * Canonical ``#RRGGBB`` brand color set as a tenant profile field,
   * or null when the tenant has not picked one yet. The app shell
   * falls back to the platform-default blue in that case.
   */
  brandColor: BrandColor | null
  /**
   * Recommended text color (``#ffffff`` or ``#111827``) for content
   * rendered on top of ``brandColor``. Computed from the supplied
   * color by a luminance check so the header text stays legible for
   * both very dark and very light brand colors.
   */
  contrastColor: '#ffffff' | '#111827' | null
  /** Whether the tenant branding record is still loading. */
  loading: boolean
  /** Last non-permission, non-404 error from the branding fetch. */
  error: string | null
  /** Re-fetch the current tenant's branding. */
  reload: () => Promise<void>
}

const BrandingContext = createContext<BrandingContextValue | null>(null)

/**
 * CSS custom property names (E10 / J3 app shell theming).
 *
 * The variables are written onto ``document.documentElement`` so any
 * rule in the global ``index.css`` (or any consumer module) can
 * reference them. The values are always cleared on unmount / when
 * branding becomes unavailable so the platform-default theme returns
 * for the next unauthenticated render (e.g. logout).
 */
const BRAND_COLOR_VAR = '--brand-color'
const BRAND_COLOR_CONTRAST_VAR = '--brand-color-contrast'
const TENANT_LOGO_URL_VAR = '--tenant-logo-url'

const _BRAND_COLOR_PATTERN = /^#[0-9A-Fa-f]{6}$/

/**
 * Parse a hex ``#RRGGBB`` string into ``[r, g, b]`` 0..255 components.
 * Returns null when the value is not a 6-digit hex string so callers
 * can fall back instead of propagating junk to the DOM.
 */
function parseHexColor(value: string): [number, number, number] | null {
  if (!_BRAND_COLOR_PATTERN.test(value)) {
    return null
  }
  const r = parseInt(value.slice(1, 3), 16)
  const g = parseInt(value.slice(3, 5), 16)
  const b = parseInt(value.slice(5, 7), 16)
  if ([r, g, b].some((component) => Number.isNaN(component))) {
    return null
  }
  return [r, g, b]
}

/**
 * Pick readable foreground color for a given background ``#RRGGBB``.
 *
 * Uses the W3C-recommended relative luminance formula (sRGB linearized
 * + the standard 0.179 threshold flipped for "text on background"
 * rather than the more common "background on text" use). When the
 * background is dark, the foreground is white; when light, near-black.
 * The output is always one of two fixed tokens (``#ffffff`` or
 * ``#111827``) so the rest of the stylesheet does not have to switch
 * between many contrast variants.
 */
function pickContrastColor(value: string): '#ffffff' | '#111827' {
  const components = parseHexColor(value)
  if (components === null) {
    return '#ffffff'
  }
  const [r, g, b] = components
  // sRGB → linear; the channels are in 0..255 so divide by 255 first.
  const linear = (channel: number): number => {
    const c = channel / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const luminance =
    0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
  // 0.5 is generous enough for typical brand palettes and keeps a
  // medium-blue brand color (e.g. #2563EB) on the dark side rather
  // than fighting with the slightly-lighter text token we use.
  return luminance < 0.5 ? '#ffffff' : '#111827'
}

function readCssVar(name: string): string | null {
  if (typeof document === 'undefined') {
    return null
  }
  const root = document.documentElement
  const value = root.style.getPropertyValue(name).trim()
  return value.length > 0 ? value : null
}

function setCssVar(name: string, value: string): void {
  if (typeof document === 'undefined') {
    return
  }
  document.documentElement.style.setProperty(name, value)
}

function clearCssVar(name: string): void {
  if (typeof document === 'undefined') {
    return
  }
  document.documentElement.style.removeProperty(name)
}

export function BrandingProvider({ children }: { children: ReactNode }) {
  const { tenant, loading, error, reload } = useTenantBranding()

  const brandColor = tenant?.brand_color ?? null
  const logoUrl = tenant?.logo_url ?? null
  const tenantName = tenant?.name ?? null
  const tenantSlug = tenant?.slug ?? null
  const tenantId = tenant?.id ?? null

  const contrastColor = useMemo(() => {
    if (brandColor === null) {
      return null
    }
    return pickContrastColor(brandColor)
  }, [brandColor])

  // Apply the brand color, contrast color, and logo URL to the document
  // root via CSS variables. This effect runs on every change of the
  // branding tuple; the values are cleared on unmount / when no
  // branding is available so the default theme takes over again.
  useEffect(() => {
    if (brandColor === null) {
      clearCssVar(BRAND_COLOR_VAR)
    } else {
      setCssVar(BRAND_COLOR_VAR, brandColor)
    }
    if (contrastColor === null) {
      clearCssVar(BRAND_COLOR_CONTRAST_VAR)
    } else {
      setCssVar(BRAND_COLOR_CONTRAST_VAR, contrastColor)
    }
    if (logoUrl === null) {
      clearCssVar(TENANT_LOGO_URL_VAR)
    } else {
      setCssVar(TENANT_LOGO_URL_VAR, `url("${logoUrl}")`)
    }
    return () => {
      clearCssVar(BRAND_COLOR_VAR)
      clearCssVar(BRAND_COLOR_CONTRAST_VAR)
      clearCssVar(TENANT_LOGO_URL_VAR)
    }
  }, [brandColor, contrastColor, logoUrl])

  const value = useMemo<BrandingContextValue>(
    () => ({
      tenantId,
      tenantName,
      tenantSlug,
      logoUrl,
      brandColor,
      contrastColor,
      loading,
      error,
      reload,
    }),
    [
      tenantId,
      tenantName,
      tenantSlug,
      logoUrl,
      brandColor,
      contrastColor,
      loading,
      error,
      reload,
    ],
  )

  return (
    <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>
  )
}

export function useBranding(): BrandingContextValue {
  const context = useContext(BrandingContext)
  if (context === null) {
    throw new Error('useBranding must be used within a BrandingProvider')
  }
  return context
}

// Exposed for unit tests that want to assert the CSS-variable
// side-effect without rendering the full provider tree. The branding
// store itself always uses the private helpers above; this is a
// low-level escape hatch only.
export const __brandingInternals = {
  BRAND_COLOR_VAR,
  BRAND_COLOR_CONTRAST_VAR,
  TENANT_LOGO_URL_VAR,
  pickContrastColor,
  parseHexColor,
  setCssVar,
  clearCssVar,
  readCssVar,
}
