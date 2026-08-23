/**
 * Frontend locale-aware currency formatter (E52; Requirements §1 Currency).
 *
 * Mirrors the contract documented for the backend helper in
 * :file:`backend/app/i18n/currency.py` (``format_currency``) so a server-
 * rendered amount and a client-rendered amount can be compared line for
 * line during reviews. The two diverge in only one respect:
 *
 * * the backend returns the canonical ``"<amount> <CODE>"`` form (because
 *   it has no per-user locale);
 * * the browser helper returns the locale-aware form
 *   ``Intl.NumberFormat`` produces (because the platform *does* know the
 *   active language through the i18next store), while still attaching the
 *   ISO 4217 code as a suffix so the rendered text is unambiguous across
 *   locales (e.g. ``"₹1,23,456.00 INR"``).
 *
 * Both sides share the same input contract — only ISO 4217 three-letter
 * uppercase codes are accepted, and anything else raises
 * :data:`InvalidCurrencyCodeError`. That single contract is the seam
 * between the backend tenant model (E52 ticket #241) and the display
 * components (this ticket, #243).
 */

const ISO_4217_CODE_PATTERN = /^[A-Z]{3}$/

export class InvalidCurrencyCodeError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'InvalidCurrencyCodeError'
  }
}

/**
 * Curated set of ISO 4217 codes the frontend recognises as well-known.
 *
 * The backend exposes this same curated list in
 * ``DEFAULT_SUPPORTED_CURRENCY_CODES`` and uses it for the dropdown on
 * the tenant-branding settings page. Keeping the frontend list in sync
 * means a tenant currency that the user can pick in the settings UI
 * also renders correctly here.
 */
export const SUPPORTED_CURRENCY_CODES = [
  'AUD',
  'CAD',
  'EUR',
  'GBP',
  'INR',
  'NZD',
  'SGD',
  'USD',
] as const

export type SupportedCurrencyCode = (typeof SUPPORTED_CURRENCY_CODES)[number]

export const DEFAULT_CURRENCY_CODE: SupportedCurrencyCode = 'INR'

/**
 * Default locale used by :func:`formatCurrencyAmount` when the caller
 * does not pass one explicitly. Matches the i18next default so the
 * formatter agrees with the language the rest of the UI is rendered
 * in. The platform does not yet store per-user locale, so falling back
 * to ``'en-IN'`` (the home market) keeps Hindi-script numerals out of
 * English sessions while still using the Indian rupee's conventional
 * grouping (``1,23,456``).
 */
export const DEFAULT_LOCALE = 'en-IN'

function isSupportedCurrencyCode(value: string): value is SupportedCurrencyCode {
  return (SUPPORTED_CURRENCY_CODES as readonly string[]).includes(value)
}

/**
 * Normalise an arbitrary currency-code input to the canonical
 * ``[A-Z]{3}`` shape the backend accepts.
 *
 * Mirrors :func:`backend.app.i18n.currency.normalize_currency_code`. The
 * helper is intentionally tolerant of whitespace and mixed case so
 * server payloads (already normalised) and freshly-typed user input
 * share a single entry point.
 */
export function normalizeCurrencyCode(code: unknown): string {
  if (typeof code !== 'string') {
    throw new InvalidCurrencyCodeError('Currency code must be a string')
  }
  const candidate = code.trim().toUpperCase()
  if (!ISO_4217_CODE_PATTERN.test(candidate)) {
    throw new InvalidCurrencyCodeError(
      'Currency code must be a 3-letter uppercase ISO 4217 code',
    )
  }
  return candidate
}

/**
 * Render ``amount`` in ``currencyCode`` using the active browser locale.
 *
 * Returns an object rather than a bare string so callers can reach for
 * the individual parts (e.g. an accessible label that needs the code
 * separately) without having to re-parse the rendered text. The
 * ``display`` string is what the user sees and is what gets surfaced
 * in the DOM as the component's text node.
 *
 * Behavior contract:
 *
 * * ``amount`` must be a finite number (or numeric string). Non-finite
 *   values (``Infinity``, ``NaN``) raise :class:`RangeError`.
 * * ``currencyCode`` must be a syntactically valid ISO 4217 code. Any
 *   other value raises :class:`InvalidCurrencyCodeError`.
 * * The output always ends with the canonical currency code so a
 *   user reading the rendered text knows exactly which currency the
 *   amount is denominated in (the locale-aware symbol on its own is
 *   not unique across locales — ``$`` is ambiguous, ``USD`` is not).
 */
export function formatCurrencyAmount(
  amount: number | string,
  currencyCode: unknown,
  options: { locale?: string } = {},
): { display: string; code: string; locale: string } {
  const code = normalizeCurrencyCode(currencyCode)
  const locale = options.locale ?? DEFAULT_LOCALE

  const numericAmount =
    typeof amount === 'string' ? Number(amount) : amount
  if (!Number.isFinite(numericAmount)) {
    throw new RangeError('Currency amount must be a finite number')
  }

  const formatter = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: code,
    currencyDisplay: 'code',
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  })

  // ``currencyDisplay: 'code'`` already appends the ISO 4217 code to
  // the formatted string (e.g. ``"USD 1,234.56"`` or ``"INR 1,23,456"``).
  // We still surface ``code`` separately so a test or accessibility
  // label does not have to re-parse the rendered text.
  const display = `${formatter.format(numericAmount)} ${code}`
  return { display, code, locale }
}

/**
 * Convenience guard: returns ``true`` when ``value`` is one of the
 * curated well-known currency codes.
 *
 * Used by the tenant-branding settings page (and any future dropdown)
 * to decide whether to render an inline warning when the server
 * returns a code the frontend does not list.
 */
export function isSupportedCurrencyCodeValue(
  value: unknown,
): value is SupportedCurrencyCode {
  return typeof value === 'string' && isSupportedCurrencyCode(value)
}
