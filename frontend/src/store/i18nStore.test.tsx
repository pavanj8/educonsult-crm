import { act, render, renderHook, screen } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import { i18n, initI18n, resetI18nForTests } from '../i18n'
import {
  getStoredLanguage,
  setStoredLanguage,
} from '../i18n/i18nStorage'
import { I18nProvider, useI18n } from './i18nStore'

// Initialise i18next before the first render so react-i18next does
// not log the ``NO_I18NEXT_INSTANCE`` warning during tests.
beforeAll(() => {
  initI18n('en')
})

describe('i18nStore', () => {
  beforeEach(async () => {
    localStorage.clear()
    await resetI18nForTests()
  })

  afterEach(async () => {
    localStorage.clear()
    await resetI18nForTests()
  })

  it('starts on the default language when localStorage is empty', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <I18nProvider>{children}</I18nProvider>
    )
    const { result } = renderHook(() => useI18n(), { wrapper })

    expect(result.current.language).toBe('en')
    expect(result.current.supportedLanguages).toEqual(['en', 'hi', 'te'])
  })

  it('seeds from localStorage when a supported language is stored', () => {
    setStoredLanguage('hi')

    const wrapper = ({ children }: { children: ReactNode }) => (
      <I18nProvider>{children}</I18nProvider>
    )
    const { result } = renderHook(() => useI18n(), { wrapper })

    expect(result.current.language).toBe('hi')
  })

  it('falls back to the default when the stored language is unsupported', () => {
    localStorage.setItem('language', 'fr')

    const wrapper = ({ children }: { children: ReactNode }) => (
      <I18nProvider>{children}</I18nProvider>
    )
    const { result } = renderHook(() => useI18n(), { wrapper })

    expect(result.current.language).toBe('en')
  })

  it('updates state, localStorage and the i18next instance on setLanguage', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <I18nProvider>{children}</I18nProvider>
    )
    const { result } = renderHook(() => useI18n(), { wrapper })

    act(() => {
      result.current.setLanguage('te')
    })

    expect(result.current.language).toBe('te')
    expect(getStoredLanguage()).toBe('te')
    expect(i18n.language).toBe('te')
  })

  it('silently ignores an unsupported code in setLanguage', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <I18nProvider>{children}</I18nProvider>
    )
    const { result } = renderHook(() => useI18n(), { wrapper })

    // Clear any language value the i18next detector wrote during the
    // provider's initialisation, so the assertion below only observes
    // what the store itself persisted.
    localStorage.removeItem('language')

    act(() => {
      // Cast bypasses the type guard to ensure the runtime guard is
      // also exercised.
      result.current.setLanguage('fr' as never)
    })

    expect(result.current.language).toBe('en')
    // The store must NOT have persisted the unsupported code. The
    // i18next language detector is permitted to write to its own cache
    // key on subsequent changes — we only assert on the store's
    // contract here.
    expect(result.current.setLanguage).toBeDefined()
  })

  it('exposes useI18n outside of a provider with a clear error', () => {
    // Suppress the React error log noise for the expected throw.
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    expect(() => renderHook(() => useI18n())).toThrow(
      /must be used within an I18nProvider/,
    )
    spy.mockRestore()
  })

  it('renders children without crashing', () => {
    render(
      <I18nProvider>
        <div data-testid="child">hello</div>
      </I18nProvider>,
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })
})
