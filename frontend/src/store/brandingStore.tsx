import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react'

import { useTenantBranding } from '../hooks/useTenantBranding'
import { pickContrastColor, type BrandColor } from './brandingColor'

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
   * falls back to the platform-default chrome in that case.
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

  // Apply the brand color + contrast color to the document root via
  // CSS variables. This effect runs on every change of the branding
  // tuple; the values are cleared on unmount / when no branding is
  // available so the default theme takes over again.
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
    return () => {
      clearCssVar(BRAND_COLOR_VAR)
      clearCssVar(BRAND_COLOR_CONTRAST_VAR)
    }
  }, [brandColor, contrastColor])

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

export { BRAND_COLOR_VAR, BRAND_COLOR_CONTRAST_VAR }
