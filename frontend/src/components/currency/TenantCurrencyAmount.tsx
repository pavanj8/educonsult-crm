import CurrencyAmount, { type CurrencyAmountProps } from './CurrencyAmount'
import { useDisplayCurrency } from './useDisplayCurrency'

export interface TenantCurrencyAmountProps extends Omit<CurrencyAmountProps, 'currencyCode'> {
  /**
   * Optional explicit currency code override. When supplied, the
   * component bypasses the tenant branding lookup and uses this code
   * directly. Intended for tests and for the rare case where a screen
   * needs to show an amount in a non-default currency (e.g. a staff
   * view comparing the tenant's INR price against a USD reference).
   */
  currencyCode?: string
}

/**
 * Currency amount component that resolves its currency from the active
 * tenant (E52; Requirements §1 Currency).
 *
 * This is the component screens should reach for by default. It pairs
 * with :func:`useDisplayCurrency` (which sits on top of the E10
 * :mod:`store/brandingStore`) and forwards the resolved code to the
 * dumb :class:`CurrencyAmount` for actual rendering.
 *
 * Behavior contract:
 *
 * * While the tenant branding record is loading (and on the login page
 *   / other pre-auth surfaces), the component falls back to
 *   :data:`DEFAULT_CURRENCY_CODE` (``'INR'``). It never renders blank.
 * * When the user is authenticated but the server returned a code
 *   outside the curated list, the component renders the fallback
 *   rather than crashing. The tenant-branding settings page surfaces
 *   the corresponding warning so the owner can correct the value.
 * * When ``currencyCode`` is supplied as a prop, the lookup is
 *   bypassed. The override path still routes through the dumb
 *   component so it gets the same validation / placeholder behavior.
 */
export default function TenantCurrencyAmount({
  currencyCode,
  ...rest
}: TenantCurrencyAmountProps) {
  const displayCurrency = useDisplayCurrency()
  const resolvedCode = currencyCode ?? displayCurrency.code

  return <CurrencyAmount {...rest} currencyCode={resolvedCode} />
}
