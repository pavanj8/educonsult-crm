import { useMemo } from 'react'

import { useBranding } from '../../store/brandingStore'
import {
  DEFAULT_CURRENCY_CODE,
  isSupportedCurrencyCodeValue,
  normalizeCurrencyCode,
  type SupportedCurrencyCode,
} from './formatCurrencyAmount'

export interface DisplayCurrency {
  /**
   * ISO 4217 three-letter currency code resolved from the active
   * tenant's branding record. Always uppercase; always three letters.
   *
   * The hook returns a value even before the tenant record has loaded
   * (and even when no user is authenticated), falling back to
   * :data:`DEFAULT_CURRENCY_CODE` so display components never have to
   * branch on ``loading`` to decide what to render.
   */
  code: string
  /**
   * Whether ``code`` was resolved from the active tenant or is a
   * frontend-side fallback. Display components can use this to render
   * a "default" badge or to skip tenant-aware features on the login
   * page and other pre-auth surfaces.
   */
  source: 'tenant' | 'fallback'
  /**
   * Whether the tenant branding record is still loading. Display
   * components that need to suppress flashes of the fallback currency
   * (e.g. an inline tag in a header) can read this and render a
   * placeholder until the true tenant code arrives.
   */
  loading: boolean
}

/**
 * Hook that exposes the active tenant's display currency code for
 * currency-aware amount components (E52 / ticket #243).
 *
 * The hook sits next to the formatting helper rather than inside the
 * branding store because (a) the branding store is owned by E10 and
 * already carries its own well-tested surface, and (b) keeping the
 * dependency narrow lets the formatter be unit-tested without spinning
 * up a branding provider.
 *
 * Resolution order:
 *
 * 1. Tenant branding record's ``currency`` field (validated against
 *    :func:`normalizeCurrencyCode`). If valid, ``source === 'tenant'``.
 * 2. :data:`DEFAULT_CURRENCY_CODE` (``'INR'``). Returned while the
 *    tenant record is loading, when no user is authenticated, or when
 *    the server returned an unrecognised code (e.g. an out-of-band
 *    admin tool set a code the curated list does not include).
 *
 * The hook never throws; it never returns ``null``; it always returns
 * a string the formatter will accept.
 */
export function useDisplayCurrency(): DisplayCurrency {
  const { tenant, loading } = useBranding()

  return useMemo<DisplayCurrency>(() => {
    const candidate = tenant?.currency ?? null
    if (candidate !== null) {
      try {
        const normalized = normalizeCurrencyCode(candidate)
        if (isSupportedCurrencyCodeValue(normalized)) {
          return { code: normalized, source: 'tenant', loading }
        }
        // Server returned a code outside the curated set — fall back
        // rather than crashing; the tenant-branding page surfaces a
        // warning in that case.
      } catch {
        // Server returned a syntactically invalid code. Fall back.
      }
    }
    return {
      code: DEFAULT_CURRENCY_CODE,
      source: 'fallback',
      loading,
    }
  }, [tenant?.currency, loading])
}
