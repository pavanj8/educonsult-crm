import { formatCurrencyAmount, InvalidCurrencyCodeError } from './formatCurrencyAmount'

export interface CurrencyAmountProps {
  /**
   * Amount to render. Accepts either a JS number or a numeric string
   * (so an API that returns ``"1234.56"`` can be passed straight
   * through without an intermediate parse). Non-finite values
   * (``NaN``, ``Infinity``) are rejected with a visible placeholder
   * rather than crashing the page.
   */
  amount: number | string
  /**
   * ISO 4217 three-letter currency code, e.g. ``'USD'``. Must be
   * uppercase and exactly three letters; any other value causes the
   * component to render a placeholder rather than throwing, so an
   * upstream bug in the tenant record cannot blank a whole page.
   */
  currencyCode: string
  /**
   * Optional locale override for the underlying ``Intl.NumberFormat``
   * call. Defaults to the platform default (``'en-IN'``) when omitted;
   * callers that already know the user's locale can pass it through.
   */
  locale?: string
  /** Optional className applied to the rendered ``<span>``. */
  className?: string
  /** Optional ``data-testid`` for E2E / unit tests. */
  testId?: string
}

const PLACEHOLDER_TEST_ID = 'currency-amount-placeholder'

/**
 * Presentational currency amount component (E52; Requirements §1 Currency).
 *
 * The dumb counterpart to :class:`TenantCurrencyAmount`: it does not
 * read the branding store. The component is intentionally tiny — its
 * only job is to take a pre-resolved ``amount`` and ``currencyCode``
 * pair, format them with :func:`formatCurrencyAmount`, and emit the
 * result as text inside a ``<span>``.
 *
 * Why a separate dumb component?
 *
 * * Unit tests can pin the rendering contract (the formatted string,
 *   the ``data-testid``, the placeholder fallback) without standing up
 *   a branding provider or an i18next instance.
 * * Storybook / catalogue / future design-system consumers can drive
 *   it with explicit inputs (e.g. ``<CurrencyAmount amount={99.95}
 *   currencyCode="EUR" />``) without a tenant context.
 * * The smart wrapper :class:`TenantCurrencyAmount` stays small and
 *   focused on its single responsibility (resolving the currency
 *   code).
 */
export default function CurrencyAmount({
  amount,
  currencyCode,
  locale,
  className,
  testId,
}: CurrencyAmountProps) {
  try {
    const { display } = formatCurrencyAmount(amount, currencyCode, { locale })
    return (
      <span
        className={className ?? 'currency-amount'}
        data-testid={testId ?? 'currency-amount'}
        data-currency-code={currencyCode.toUpperCase()}
      >
        {display}
      </span>
    )
  } catch (error) {
    // The component never throws upward — it renders a placeholder
    // span instead so a bug in one tenant's currency field cannot
    // blank an entire page. We deliberately log only the message (no
    // stack) to keep the production console quiet; tests assert on
    // the placeholder testid.
    if (error instanceof InvalidCurrencyCodeError) {
      // eslint-disable-next-line no-console
      console.warn(`CurrencyAmount: invalid currency code "${currencyCode}"`)
    } else {
      // eslint-disable-next-line no-console
      console.warn(`CurrencyAmount: could not format ${String(amount)} ${currencyCode}`)
    }
    return (
      <span
        className={className ?? 'currency-amount currency-amount--invalid'}
        data-testid={testId ? `${testId}-placeholder` : PLACEHOLDER_TEST_ID}
      >
        —
      </span>
    )
  }
}
