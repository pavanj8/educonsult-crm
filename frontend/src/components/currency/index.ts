/**
 * Public entry point for the currency-aware amount display components
 * (E52; ticket #243 — "Frontend: currency-aware amount display
 * components").
 *
 * Screens and design-system consumers import from here (e.g.
 * ``import { TenantCurrencyAmount } from '.../components/currency'``)
 * rather than reaching into individual files, so the implementation
 * detail of which file owns which symbol can evolve without touching
 * call sites.
 */

export { default as CurrencyAmount } from './CurrencyAmount'
export type { CurrencyAmountProps } from './CurrencyAmount'

export { default as TenantCurrencyAmount } from './TenantCurrencyAmount'
export type { TenantCurrencyAmountProps } from './TenantCurrencyAmount'

export { useDisplayCurrency } from './useDisplayCurrency'
export type { DisplayCurrency } from './useDisplayCurrency'

export {
  DEFAULT_CURRENCY_CODE,
  DEFAULT_LOCALE,
  InvalidCurrencyCodeError,
  SUPPORTED_CURRENCY_CODES,
  formatCurrencyAmount,
  isSupportedCurrencyCodeValue,
  normalizeCurrencyCode,
} from './formatCurrencyAmount'
export type { SupportedCurrencyCode } from './formatCurrencyAmount'
