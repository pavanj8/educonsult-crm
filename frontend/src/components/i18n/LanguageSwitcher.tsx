import { useTranslation } from 'react-i18next'

import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '../../i18n'
import { useI18n } from '../../store/i18nStore'

/**
 * User-facing display label for each language code (E51 ticket #238).
 *
 * The labels are intentionally in the language's own script so a user
 * recognises their language at a glance regardless of which language
 * the rest of the UI is currently rendered in. English is kept in
 * Latin script because that's what Hindi / Telugu speakers would type
 * to refer to "English".
 */
const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: 'English',
  hi: 'हिन्दी',
  te: 'తెలుగు',
}

const TEST_ID = 'language-switcher'
const LABEL_TEST_ID = 'language-switcher-label'

export default function LanguageSwitcher() {
  const { language, setLanguage } = useI18n()
  const { t } = useTranslation()

  function handleChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const next = event.target.value as SupportedLanguage
    setLanguage(next)
  }

  return (
    <div className="language-switcher" data-testid={TEST_ID}>
      <label
        className="language-switcher__label"
        data-testid={LABEL_TEST_ID}
        htmlFor="language-switcher-select"
      >
        {t('languageSwitcher.label')}
      </label>
      <select
        id="language-switcher-select"
        className="language-switcher__select"
        data-testid="language-switcher-select"
        value={language}
        onChange={handleChange}
        aria-label={t('languageSwitcher.label')}
      >
        {SUPPORTED_LANGUAGES.map((code) => (
          <option
            key={code}
            value={code}
            data-testid={`language-switcher-option-${code}`}
          >
            {LANGUAGE_LABELS[code]}
          </option>
        ))}
      </select>
    </div>
  )
}
