/**
 * i18next configuration and initializer (E51 / Requirements §1 i18n).
 *
 * Scope of this ticket (#238 — "Frontend: set up i18next framework +
 * language switcher"):
 *
 *   * Wire up the i18next runtime (this file) and a thin React store
 *     (:file:`frontend/src/store/i18nStore.tsx`) so the rest of the
 *     app can call ``useTranslation()`` once the sibling
 *     string-extraction ticket (#239) lands.
 *   * Ship the three target locales — English, Hindi, Telugu — so the
 *     language switcher actually has languages to switch to.
 *   * Persist the chosen language across reloads so the platform does
 *     not flicker back to English on every page navigation.
 *
 * Out of scope here (covered by sibling tickets):
 *   * Translating the rest of the UI strings — ticket #239
 *     ("extract existing UI strings into translation keys").
 *   * Adding Hindi / Telugu translations for those extracted strings —
 *     ticket #240 ("Add Hindi and Telugu translation files"). The
 *     resources below carry only the keys the language switcher itself
 *     needs; missing keys will fall back to English through i18next's
 *     default ``fallbackLng`` behaviour until #240 fills them in.
 */

import i18next, { type i18n as I18nInstance } from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  type SupportedLanguage,
} from './i18nStorage'

import enCommon from './locales/en/common.json'
import hiCommon from './locales/hi/common.json'
import teCommon from './locales/te/common.json'

export {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
} from './i18nStorage'
export type { SupportedLanguage } from './i18nStorage'

/**
 * The single shared ``i18next`` instance used by the React provider.
 *
 * i18next is a module-level singleton; creating one per test or per
 * provider would defeat both the cache and the language-detector
 * plugin. Tests reach in and reset this module via ``resetI18nForTests``
 * so each test starts from a known language state.
 */
export const i18n: I18nInstance = i18next

/**
 * Resource bundle for the three target locales, addressed by their
 * primary subtag. ``fallbackLng: 'en'`` means any key missing in Hindi
 * or Telugu silently falls back to English until ticket #240 lands
 * (which adds the Hindi / Telugu translations).
 */
const RESOURCES = {
  en: { common: enCommon },
  hi: { common: hiCommon },
  te: { common: teCommon },
} as const

/**
 * Initialise the shared ``i18next`` instance.
 *
 * Idempotent: calling this twice (e.g. on Fast Refresh) is safe — the
 * second call simply replaces the language + resources in place. The
 * store layer calls this once on mount.
 */
export function initI18n(initialLanguage: SupportedLanguage = DEFAULT_LANGUAGE): I18nInstance {
  if (i18next.isInitialized) {
    void i18next.changeLanguage(initialLanguage)
    return i18next
  }

  void i18next
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
      resources: RESOURCES,
      lng: initialLanguage,
      fallbackLng: DEFAULT_LANGUAGE,
      supportedLngs: SUPPORTED_LANGUAGES as readonly string[],
      nonExplicitSupportedLngs: true,
      defaultNS: 'common',
      ns: ['common'],
      interpolation: {
        // React already escapes values in JSX — turning this off keeps
        // any future string interpolation expressions (e.g. ``{{name}}``)
        // raw so a tenant-supplied name cannot accidentally inject
        // markup.
        escapeValue: false,
      },
      // ``debug`` is intentionally off in production builds; flip it on
      // via the standard i18next debug environment knob when triaging
      // missing-key reports.
      debug: false,
      // The detector's caches are still useful for SSR / first-paint
      // detection but we rely on the explicit ``initialLanguage`` from
      // the store (which consults localStorage) as the source of truth.
      detection: {
        order: ['localStorage', 'navigator'],
        caches: ['localStorage'],
        lookupLocalStorage: 'language',
      },
    })

  return i18next
}

/**
 * Reset the shared i18next instance to a known state. Tests use this
 * between cases so a ``changeLanguage`` in one test does not bleed into
 * the next; the production code path never calls it.
 *
 * NOTE: This module deliberately does NOT call ``initI18n`` at import
 * time. The provider (:file:`frontend/src/store/i18nStore.tsx`) owns
 * initialisation on mount, and unit tests that render a single page in
 * isolation (e.g. ``LoginPage.test.tsx``, ``AppLayout.test.tsx``) call
 * ``initI18n`` themselves in ``beforeAll`` so the first render of
 * ``useTranslation()`` never sees an uninitialised i18next instance.
 * This keeps the init lifecycle single-sourced and lets tests reset
 * the language between cases without racing a hot module reload.
 */
export async function resetI18nForTests(): Promise<void> {
  if (i18next.isInitialized) {
    await i18next.changeLanguage(DEFAULT_LANGUAGE)
  }
}
