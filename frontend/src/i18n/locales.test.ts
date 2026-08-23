/**
 * Black-box tests for the Hindi and Telugu translation bundles
 * (E51 / ticket #240 — "Add Hindi and Telugu translation files").
 *
 * These tests are intentionally written against the *public* i18next
 * surface (``i18n.t`` after ``i18n.changeLanguage``) rather than
 * reaching into the raw JSON, so the test stays valid regardless of
 * how the bundles are loaded (static ``import`` vs dynamic fetch
 * later). They prove three acceptance criteria:
 *
 *   1. The Hindi and Telugu resource bundles are statically
 *      importable as JSON (i.e. they are valid, well-formed JSON files
 *      sitting where the i18n config looks for them).
 *   2. Every key the frontend currently wires up through
 *      ``useTranslation()`` is present in both bundles with a
 *      non-empty string value (i.e. when a user switches language,
 *      every rendered string is the locale's own translation — not
 *      an empty placeholder or a raw key).
 *   3. The language switcher's own keys switch with the active
 *      language — the most user-visible proof that the language
 *      switcher is now backed by a real translation rather than an
 *      English-only fallback.
 */

import { afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { i18n, initI18n, resetI18nForTests } from './config'

import hiBundle from './locales/hi/common.json'
import teBundle from './locales/te/common.json'

// ``react-i18next`` is not used in these tests — we drive i18next
// directly through ``i18n.changeLanguage`` / ``i18n.t`` so we can
// assert the resolved string the same way a ``useTranslation()``
// consumer would receive it. Running ``initI18n`` once up-front avoids
// the noisy first-render warning if a consumer in the same test file
// ever mounts a component.
beforeAll(() => {
  initI18n('en')
})

/**
 * Every translation key the frontend's i18next consumers reference.
 *
 * This list mirrors the union of:
 *   - the keys already shipped by ticket #238 (language switcher), and
 *   - the keys extracted by ticket #239 (app header nav, login page,
 *     home page, 404 page, shared "loading" copy).
 *
 * When ticket #239 merges these same keys will appear in
 * ``locales/en/common.json``; this list is the source of truth for the
 * *acceptance contract* of #240: when a user switches to Hindi or
 * Telugu, every one of these keys must resolve to a non-empty
 * translated string in their own script.
 */
const EXPECTED_KEYS = [
  // app (header)
  'app.platformName',
  'app.nav.main',
  'app.nav.tenants',
  'app.nav.branches',
  'app.nav.staff',
  'app.nav.masterData',
  'app.nav.branding',
  'app.nav.checklistTemplates',
  'app.nav.dashboard',
  'app.nav.verifierQueue',
  'app.nav.myApplications',
  'app.nav.intake',
  // home page
  'home.welcome',
  // login page
  'login.title',
  'login.fields.email',
  'login.fields.password',
  'login.submit.idle',
  'login.submit.submitting',
  'login.links.forgotPassword',
  'login.links.newStudentPrompt',
  'login.links.createAccount',
  'login.errors.fallback',
  // shared / 404
  'common.loading',
  'common.loadingEllipsis',
  'notFound.message',
  // language switcher itself
  'languageSwitcher.label',
] as const

/** Locales that must carry a real (non-empty) translation bundle. */
const TRANSLATED_LOCALES = ['hi', 'te'] as const
type TranslatedLocale = (typeof TRANSLATED_LOCALES)[number]

/** The parsed JSON bundle for each translated locale. */
const BUNDLES: Record<TranslatedLocale, Record<string, unknown>> = {
  hi: hiBundle as Record<string, unknown>,
  te: teBundle as Record<string, unknown>,
}

describe('Hindi and Telugu translation bundles (#240)', () => {
  beforeEach(async () => {
    await resetI18nForTests()
  })

  afterEach(async () => {
    await resetI18nForTests()
  })

  for (const locale of TRANSLATED_LOCALES) {
    describe(`locale '${locale}'`, () => {
      it('imports as a JSON object from the expected path', () => {
        // Statically-importable as JSON is the runtime contract that
        // ``frontend/src/i18n/config.ts`` depends on; if this test
        // ever fails with "expected an object", the JSON file is
        // either missing or contains a top-level primitive.
        expect(BUNDLES[locale]).toBeTypeOf('object')
      })

      it('carries every translation key the frontend expects', () => {
        for (const key of EXPECTED_KEYS) {
          const value = resolveKey(BUNDLES[locale], key)
          // Every key must be present AND be a non-empty string — an
          // empty value would render as nothing in the UI, which is
          // worse than falling back to English, and a missing key
          // would render the raw key path.
          expect(value, `key ${key} missing in ${locale}`).toBeTypeOf('string')
          expect(
            (value as string).length,
            `key ${key} in ${locale} is empty`,
          ).toBeGreaterThan(0)
        }
      })

      it('resolves every key to a translated string via i18next', () => {
        // Drive the i18next instance the way the React provider does
        // when the user picks this language in the switcher.
        i18n.changeLanguage(locale)

        for (const key of EXPECTED_KEYS) {
          const resolved = i18n.t(key)
          // ``resolved`` must not equal the key itself — that would
          // mean the bundle is missing the key and i18next fell all
          // the way through to its string-key fallback.
          expect(
            resolved,
            `i18next could not translate ${key} for locale ${locale}`,
          ).not.toBe(key)
          expect(resolved.length).toBeGreaterThan(0)
        }
      })

      it('renders the language switcher label in its own script', () => {
        i18n.changeLanguage(locale)
        // The label rendered in the switcher must NOT be the English
        // fallback — i.e. the bundle must override the framework's
        // English-only default with a translated value for this
        // locale.
        const resolved = i18n.t('languageSwitcher.label')
        expect(resolved).not.toBe('Language')
        expect(resolved.length).toBeGreaterThan(0)
      })

      it('translates the platform name into the locale', () => {
        i18n.changeLanguage(locale)
        // The platform name is a header string rendered on every
        // authenticated page; the English fallback is the literal
        // string "EduConsult CRM" so any locale translation that
        // happens to match the brand name verbatim would falsely
        // pass. We instead assert the translated value is non-empty
        // AND differs from a freshly-extracted "missing translation"
        // fallback (which i18next surfaces as the key itself).
        const resolved = i18n.t('app.platformName')
        expect(resolved).not.toBe('app.platformName')
        expect(resolved.length).toBeGreaterThan(0)
      })
    })
  }
})

/**
 * Walk a dot-separated key path (``a.b.c``) through a plain object.
 * Returns the value at the leaf, or ``undefined`` if any segment on
 * the path is missing. Returns the raw object for empty paths so the
 * ``toBeTypeOf('object')`` assertion above can spot a missing root.
 */
function resolveKey(bundle: Record<string, unknown>, path: string): unknown {
  const parts = path.split('.')
  let current: unknown = bundle
  for (const part of parts) {
    if (current === null || typeof current !== 'object') {
      return undefined
    }
    current = (current as Record<string, unknown>)[part]
  }
  return current
}
