import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  type SupportedLanguage,
  i18n,
  initI18n,
} from '../i18n'
import { getStoredLanguage, setStoredLanguage } from '../i18n/i18nStorage'

type I18nContextValue = {
  /** Currently-active language code (one of ``SUPPORTED_LANGUAGES``). */
  language: SupportedLanguage
  /** The full list of languages the switcher exposes. */
  supportedLanguages: readonly SupportedLanguage[]
  /**
   * Switch to ``language`` and persist the choice in ``localStorage``.
   * Silently no-ops on an unsupported code so the language switcher
   * cannot put the platform into a broken state.
   */
  setLanguage: (language: SupportedLanguage) => void
}

const I18nContext = createContext<I18nContextValue | null>(null)

/**
 * Provider that owns the active language and synchronises it with the
 * shared ``i18next`` instance plus ``localStorage``.
 *
 * The store deliberately does NOT call ``initI18n`` at module import
 * time so unit tests can reset i18next between cases (via
 * ``resetI18nForTests``) without racing a hot module reload. The first
 * render of the provider runs the initialiser exactly once and seeds
 * the language from localStorage, falling back to the platform default.
 */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<SupportedLanguage>(DEFAULT_LANGUAGE)

  // Run the i18next initialiser once on mount with the language stored
  // in localStorage (if any). Subscribing to i18next's ``languageChanged``
  // event keeps the React state in lock-step with any external change
  // (e.g. a future ``<html lang>`` observer, tests calling
  // ``i18n.changeLanguage`` directly).
  useEffect(() => {
    const initial = getStoredLanguage() ?? DEFAULT_LANGUAGE
    initI18n(initial)
    setLanguageState(initial)

    function handleLanguageChanged(next: string) {
      if (
        (SUPPORTED_LANGUAGES as readonly string[]).includes(next)
      ) {
        setLanguageState(next as SupportedLanguage)
      }
    }

    i18n.on('languageChanged', handleLanguageChanged)
    return () => {
      i18n.off('languageChanged', handleLanguageChanged)
    }
  }, [])

  const setLanguage = useCallback((next: SupportedLanguage) => {
    if (!(SUPPORTED_LANGUAGES as readonly string[]).includes(next)) {
      return
    }
    setStoredLanguage(next)
    void i18n.changeLanguage(next)
    setLanguageState(next)
  }, [])

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      supportedLanguages: SUPPORTED_LANGUAGES,
      setLanguage,
    }),
    [language, setLanguage],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext)
  if (context === null) {
    throw new Error('useI18n must be used within an I18nProvider')
  }
  return context
}
