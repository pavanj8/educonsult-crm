/**
 * Public entry point for the i18n module.
 *
 * Components import from here (e.g. ``import { useI18n, SUPPORTED_LANGUAGES } from '.../i18n'``)
 * rather than reaching into ``config.ts`` / ``i18nStorage.ts`` directly,
 * so the implementation detail of which file owns which constant can
 * evolve without touching consumers.
 */

export {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  i18n,
  initI18n,
  resetI18nForTests,
} from './config'
export type { SupportedLanguage } from './config'
export {
  clearStoredLanguage,
  getStoredLanguage,
  setStoredLanguage,
} from './i18nStorage'
