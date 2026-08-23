import { beforeEach, describe, expect, it } from 'vitest'

import {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  clearStoredLanguage,
  getStoredLanguage,
  setStoredLanguage,
} from './i18nStorage'

describe('i18nStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('exposes the platform default language', () => {
    expect(DEFAULT_LANGUAGE).toBe('en')
  })

  it('exposes the supported language set', () => {
    expect(SUPPORTED_LANGUAGES).toEqual(['en', 'hi', 'te'])
  })

  describe('getStoredLanguage', () => {
    it('returns null when nothing has been stored', () => {
      expect(getStoredLanguage()).toBeNull()
    })

    it('returns the stored language for a supported code', () => {
      localStorage.setItem('language', 'hi')
      expect(getStoredLanguage()).toBe('hi')
    })

    it('returns null for an unsupported code', () => {
      // A stale value from a previous build (e.g. a language that was
      // later removed) must not be returned to the caller — the store
      // will fall back to the default rather than render in a dead
      // language.
      localStorage.setItem('language', 'fr')
      expect(getStoredLanguage()).toBeNull()
    })
  })

  describe('setStoredLanguage', () => {
    it('persists a supported language code', () => {
      setStoredLanguage('te')
      expect(localStorage.getItem('language')).toBe('te')
    })

    it('ignores an unsupported code', () => {
      // ``fr`` is not in the supported set; the store guard must
      // refuse to persist it so a stale value never resurrects itself.
      setStoredLanguage('fr' as never)
      expect(localStorage.getItem('language')).toBeNull()
    })
  })

  describe('clearStoredLanguage', () => {
    it('removes the stored language', () => {
      setStoredLanguage('hi')
      clearStoredLanguage()
      expect(localStorage.getItem('language')).toBeNull()
      expect(getStoredLanguage()).toBeNull()
    })
  })
})
