/**
 * LocalStorage helpers for the persisted language preference (E51; J-§1 i18n).
 *
 * Mirrors the convention established by ``authStorage.ts`` so all
 * client-persisted user preferences share the same thin, side-effect-free
 * adapter. Keeping this in its own module lets the store / switcher
 * component depend on a single, easily-mocked surface and lets unit tests
 * pin the localStorage contract independently from React.
 */

const LANGUAGE_KEY = 'language'

/**
 * The full set of languages the frontend supports in this iteration.
 *
 * The codes match the BCP 47 primary subtag so they line up with the
 * ``i18next`` locale identifiers and with the per-locale resource files
 * in :file:`frontend/src/i18n/locales/`. Adding a fourth language later
 * is a single-line change here plus a new JSON file (E51 ticket #240).
 */
export const SUPPORTED_LANGUAGES = ['en', 'hi', 'te'] as const

export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]

export const DEFAULT_LANGUAGE: SupportedLanguage = 'en'

function isSupportedLanguage(value: string): value is SupportedLanguage {
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(value)
}

/**
 * Read the persisted language from ``localStorage``.
 *
 * Returns ``null`` when nothing is stored or the stored value is not one
 * of the supported languages — the caller (the store) falls back to the
 * platform default in that case rather than silently picking an
 * arbitrary language.
 */
export function getStoredLanguage(): SupportedLanguage | null {
  const value = localStorage.getItem(LANGUAGE_KEY)
  if (value === null) {
    return null
  }
  return isSupportedLanguage(value) ? value : null
}

/**
 * Persist the language preference to ``localStorage``.
 *
 * Passing a value outside :data:`SUPPORTED_LANGUAGES` is silently
 * rejected — the store has already validated the value against the
 * supported set before reaching this point, and silently storing an
 * unknown code would resurrect it on the next page load.
 */
export function setStoredLanguage(language: SupportedLanguage): void {
  if (!isSupportedLanguage(language)) {
    return
  }
  localStorage.setItem(LANGUAGE_KEY, language)
}

export function clearStoredLanguage(): void {
  localStorage.removeItem(LANGUAGE_KEY)
}
