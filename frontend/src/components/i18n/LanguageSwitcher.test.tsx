import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { I18nProvider } from '../../store/i18nStore'
import { SUPPORTED_LANGUAGES, initI18n, resetI18nForTests } from '../../i18n'
import { getStoredLanguage } from '../../i18n/i18nStorage'
import LanguageSwitcher from './LanguageSwitcher'

// ``react-i18next`` looks up the i18next instance on first render of
// ``useTranslation``. The provider's ``useEffect`` runs *after* the
// first render, so we must initialise the shared instance up-front to
// avoid the noisy ``NO_I18NEXT_INSTANCE`` warning during the first
// render in tests.
beforeAll(() => {
  initI18n('en')
})

function Harness() {
  return (
    <I18nProvider>
      <LanguageSwitcher />
    </I18nProvider>
  )
}

describe('LanguageSwitcher', () => {
  beforeEach(async () => {
    localStorage.clear()
    await resetI18nForTests()
  })

  afterEach(async () => {
    localStorage.clear()
    await resetI18nForTests()
  })

  it('renders one option per supported language', () => {
    render(<Harness />)

    const select = screen.getByTestId('language-switcher-select')
    for (const code of SUPPORTED_LANGUAGES) {
      const option = screen.getByTestId(`language-switcher-option-${code}`)
      expect(option).toBeInstanceOf(HTMLOptionElement)
      expect((option as HTMLOptionElement).value).toBe(code)
    }
    // Sanity: the select element holds exactly the supported set.
    expect(select.querySelectorAll('option')).toHaveLength(SUPPORTED_LANGUAGES.length)
  })

  it('reflects the currently-active language in the select value', () => {
    render(<Harness />)

    const select = screen.getByTestId(
      'language-switcher-select',
    ) as HTMLSelectElement
    // The provider seeds from localStorage (cleared in beforeEach) so
    // the default language is active.
    expect(select.value).toBe('en')
  })

  it('updates the active language, the select, and localStorage on change', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    const select = screen.getByTestId(
      'language-switcher-select',
    ) as HTMLSelectElement

    await user.selectOptions(select, 'hi')

    expect(select.value).toBe('hi')
    expect(getStoredLanguage()).toBe('hi')
  })

  it('renders a label that is wired through i18next', () => {
    render(<Harness />)

    // The English resource carries the canonical label.
    expect(screen.getByTestId('language-switcher-label')).toHaveTextContent(
      'Language',
    )
  })
})
