import { describe, expect, it } from 'vitest'

import {
  DEFAULT_CURRENCY_CODE,
  DEFAULT_LOCALE,
  InvalidCurrencyCodeError,
  SUPPORTED_CURRENCY_CODES,
  formatCurrencyAmount,
  isSupportedCurrencyCodeValue,
  normalizeCurrencyCode,
} from './formatCurrencyAmount'

describe('normalizeCurrencyCode', () => {
  it('uppercases lowercase input', () => {
    expect(normalizeCurrencyCode('usd')).toBe('USD')
  })

  it('strips surrounding whitespace', () => {
    expect(normalizeCurrencyCode('  inr  ')).toBe('INR')
  })

  it('passes through valid uppercase codes', () => {
    expect(normalizeCurrencyCode('AUD')).toBe('AUD')
  })

  it('accepts any syntactically-valid 3-letter uppercase ISO 4217 code', () => {
    // The formatter accepts any valid shape; the curated list is just
    // the *well-known* set. JPY / CHF are syntactically valid even
    // though they are not part of the curated list.
    expect(normalizeCurrencyCode('JPY')).toBe('JPY')
    expect(normalizeCurrencyCode('CHF')).toBe('CHF')
  })

  it.each<[unknown, string]>([
    ['', 'empty string'],
    ['us', 'too short'],
    ['usdd', 'too long'],
    ['us1', 'contains a digit'],
    ['123', 'all digits'],
    ['US-', 'contains a hyphen'],
    ['us$', 'contains a symbol'],
    [null, 'null'],
    [undefined, 'undefined'],
    [42, 'number'],
    [{ code: 'USD' }, 'object'],
  ])('rejects %s (%s)', (input) => {
    expect(() => normalizeCurrencyCode(input)).toThrow(InvalidCurrencyCodeError)
  })
})

describe('isSupportedCurrencyCodeValue', () => {
  it('returns true for every code in the curated set', () => {
    for (const code of SUPPORTED_CURRENCY_CODES) {
      expect(isSupportedCurrencyCodeValue(code)).toBe(true)
    }
  })

  it('returns false for codes outside the curated set', () => {
    expect(isSupportedCurrencyCodeValue('JPY')).toBe(false)
    expect(isSupportedCurrencyCodeValue('CHF')).toBe(false)
  })

  it('returns false for lowercase codes (case-sensitive on purpose)', () => {
    // ``normalizeCurrencyCode`` is the entry point that case-folds; this
    // guard intentionally checks the curated set as-is so it can be
    // used without first normalising.
    expect(isSupportedCurrencyCodeValue('usd')).toBe(false)
  })

  it('returns false for non-string inputs', () => {
    expect(isSupportedCurrencyCodeValue(null)).toBe(false)
    expect(isSupportedCurrencyCodeValue(undefined)).toBe(false)
    expect(isSupportedCurrencyCodeValue(42)).toBe(false)
  })
})

describe('formatCurrencyAmount', () => {
  it('returns the canonical display, code, and locale fields', () => {
    const result = formatCurrencyAmount(1234.56, 'USD')
    expect(result.code).toBe('USD')
    expect(result.locale).toBe(DEFAULT_LOCALE)
    expect(typeof result.display).toBe('string')
    expect(result.display).toContain('USD')
    // The display must surface the numeric amount, not just the code.
    // ``Intl.NumberFormat('en-IN', { currency: 'USD' })`` renders
    // thousands separators; we assert on the substring rather than the
    // exact punctuation so a future ICU data update cannot break the
    // test for an unrelated reason.
    expect(result.display).toMatch(/1,234\.56/)
  })

  it('surfaces the ISO 4217 code exactly once in the rendered display', () => {
    // Regression guard: ``Intl.NumberFormat({ currencyDisplay: 'code' })``
    // already appends the code, so the formatter must not double it.
    // A previous iteration appended ``${code}`` a second time, which
    // rendered e.g. ``"USD 1,234.56 USD"`` for every amount and would
    // have been a visible UX bug.
    const usd = formatCurrencyAmount(1234.56, 'USD')
    expect(usd.display).not.toMatch(/USD.*USD/)
    // ``Intl.NumberFormat`` joins the code and amount with a
    // non-breaking space (``\u00A0``), not a regular space. Assert on
    // the substring with the literal separator so we exercise the
    // same code path users see, regardless of ICU punctuation tweaks.
    expect(usd.display).toContain('USD\u00A01,234.56')
    expect(usd.display.endsWith('USD\u00A01,234.56')).toBe(true)

    const inr = formatCurrencyAmount(123456, 'INR')
    expect(inr.display).not.toMatch(/INR.*INR/)
    expect(inr.display).toContain('INR\u00A01,23,456')
  })

  it('renders integer amounts without a fractional part', () => {
    const result = formatCurrencyAmount(1000, 'EUR')
    expect(result.display).toMatch(/1,000(?!\.)/)
  })

  it('accepts numeric strings as the amount', () => {
    const result = formatCurrencyAmount('1234.56', 'USD')
    expect(result.display).toMatch(/1,234\.56/)
  })

  it('normalises mixed-case currency codes', () => {
    const result = formatCurrencyAmount(100, 'inr')
    expect(result.code).toBe('INR')
    expect(result.display).toContain('INR')
  })

  it('honours an explicit locale override', () => {
    const result = formatCurrencyAmount(1234.56, 'USD', { locale: 'en-US' })
    expect(result.locale).toBe('en-US')
    // ``en-US`` uses a comma as the thousands separator and a period
    // for the decimal — same as ``en-IN`` for this amount.
    expect(result.display).toMatch(/1,234\.56/)
  })

  it('rejects non-finite amounts', () => {
    expect(() => formatCurrencyAmount(NaN, 'USD')).toThrow(RangeError)
    expect(() => formatCurrencyAmount(Infinity, 'USD')).toThrow(RangeError)
  })

  it('rejects invalid currency codes', () => {
    expect(() => formatCurrencyAmount(100, 'us')).toThrow(InvalidCurrencyCodeError)
    expect(() => formatCurrencyAmount(100, '123')).toThrow(InvalidCurrencyCodeError)
    expect(() => formatCurrencyAmount(100, null)).toThrow(InvalidCurrencyCodeError)
  })

  it('exports the default currency and locale constants', () => {
    expect(DEFAULT_CURRENCY_CODE).toBe('INR')
    expect(typeof DEFAULT_LOCALE).toBe('string')
    expect(DEFAULT_LOCALE.length).toBeGreaterThan(0)
  })

  it('the curated SUPPORTED_CURRENCY_CODES list matches the backend set', () => {
    // Pin the curated set so an accidental drift between the frontend
    // dropdown (TenantBrandingPage) and this module fails loudly here.
    expect([...SUPPORTED_CURRENCY_CODES].sort()).toEqual(
      ['AUD', 'CAD', 'EUR', 'GBP', 'INR', 'NZD', 'SGD', 'USD'],
    )
  })
})
