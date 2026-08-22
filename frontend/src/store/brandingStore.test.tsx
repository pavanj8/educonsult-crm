import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import { BrandingProvider, useBranding, __brandingInternals } from './brandingStore'
import { AuthProvider } from './authStore'

const {
  BRAND_COLOR_VAR,
  BRAND_COLOR_CONTRAST_VAR,
  TENANT_LOGO_URL_VAR,
  setCssVar,
  clearCssVar,
} = __brandingInternals

const superAdminUser = {
  id: 1,
  email: 'admin@demo.test',
  role: 'super_admin' as const,
  tenant_id: 7,
  branch_id: null,
}

const brandedTenant = {
  id: 7,
  name: 'Apex EduConsult',
  slug: 'apex',
  logo_url: 'https://cdn.example.test/apex/logo.png',
  brand_color: '#1A2B3C',
  currency: 'USD',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

function wrapper({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <BrandingProvider>{children}</BrandingProvider>
    </AuthProvider>
  )
}

describe('BrandingProvider', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    document.documentElement.removeAttribute('style')
  })

  afterEach(() => {
    document.documentElement.removeAttribute('style')
  })

  it('exposes no branding values when no user is authenticated', async () => {
    const { result } = renderHook(() => useBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.brandColor).toBeNull()
    expect(result.current.contrastColor).toBeNull()
    expect(result.current.logoUrl).toBeNull()
    expect(result.current.tenantName).toBeNull()
    expect(result.current.tenantId).toBeNull()

    // CSS variables are left untouched when there's no brand color so
    // the platform-default stylesheet theme applies.
    expect(document.documentElement.style.getPropertyValue(BRAND_COLOR_VAR)).toBe('')
    expect(
      document.documentElement.style.getPropertyValue(BRAND_COLOR_CONTRAST_VAR),
    ).toBe('')
  })

  it('writes the brand color and contrast variable for a branded tenant', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => superAdminUser,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => brandedTenant,
      }) as typeof fetch

    const { result } = renderHook(() => useBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.brandColor).toBe('#1A2B3C')
    })

    expect(result.current.contrastColor).toBe('#ffffff')
    expect(result.current.logoUrl).toBe('https://cdn.example.test/apex/logo.png')
    expect(result.current.tenantName).toBe('Apex EduConsult')
    expect(result.current.tenantSlug).toBe('apex')
    expect(result.current.tenantId).toBe(7)

    expect(document.documentElement.style.getPropertyValue(BRAND_COLOR_VAR)).toBe('#1A2B3C')
    expect(
      document.documentElement.style.getPropertyValue(BRAND_COLOR_CONTRAST_VAR),
    ).toBe('#ffffff')
    expect(
      document.documentElement.style.getPropertyValue(TENANT_LOGO_URL_VAR),
    ).toBe('url("https://cdn.example.test/apex/logo.png")')
  })

  it('clears CSS variables when branding becomes unavailable (logout)', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => superAdminUser,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => brandedTenant,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Insufficient permissions' }),
      }) as typeof fetch

    const { result } = renderHook(() => useBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.brandColor).toBe('#1A2B3C')
    })

    // Clear the auth token so the next load() resolves with
    // tenant_id === null — simulating the post-logout state without
    // having to plumb logout through both providers.
    act(() => {
      localStorage.clear()
    })

    // Force a reload while the user is unauthenticated; the hook is
    // still alive because the provider mounts before the auth state
    // is cleared in the same tick.
    await act(async () => {
      await result.current.reload()
    })

    await waitFor(() => {
      expect(result.current.brandColor).toBeNull()
    })

    expect(document.documentElement.style.getPropertyValue(BRAND_COLOR_VAR)).toBe('')
    expect(
      document.documentElement.style.getPropertyValue(BRAND_COLOR_CONTRAST_VAR),
    ).toBe('')
    expect(
      document.documentElement.style.getPropertyValue(TENANT_LOGO_URL_VAR),
    ).toBe('')
  })
})

describe('branding internals', () => {
  beforeEach(() => {
    document.documentElement.removeAttribute('style')
  })

  afterEach(() => {
    document.documentElement.removeAttribute('style')
  })

  it('picks white text on dark backgrounds', () => {
    expect(__brandingInternals.pickContrastColor('#000000')).toBe('#ffffff')
    expect(__brandingInternals.pickContrastColor('#1A2B3C')).toBe('#ffffff')
    expect(__brandingInternals.pickContrastColor('#2563EB')).toBe('#ffffff')
  })

  it('picks dark text on light backgrounds', () => {
    expect(__brandingInternals.pickContrastColor('#FFFFFF')).toBe('#111827')
    expect(__brandingInternals.pickContrastColor('#FAFAFA')).toBe('#111827')
    expect(__brandingInternals.pickContrastColor('#FFD700')).toBe('#111827')
  })

  it('falls back to white contrast for malformed inputs', () => {
    expect(__brandingInternals.pickContrastColor('not-a-color')).toBe('#ffffff')
    expect(__brandingInternals.pickContrastColor('#FFF')).toBe('#ffffff')
  })

  it('parses valid hex colors', () => {
    expect(__brandingInternals.parseHexColor('#1A2B3C')).toEqual([26, 43, 60])
    expect(__brandingInternals.parseHexColor('#abcdef')).toEqual([0xab, 0xcd, 0xef])
  })

  it('rejects malformed hex colors', () => {
    expect(__brandingInternals.parseHexColor('1A2B3C')).toBeNull()
    expect(__brandingInternals.parseHexColor('#FFF')).toBeNull()
    expect(__brandingInternals.parseHexColor('#ZZZZZZ')).toBeNull()
  })

  it('sets and clears CSS variables via the helpers', () => {
    setCssVar('--test-var', 'red')
    expect(document.documentElement.style.getPropertyValue('--test-var')).toBe('red')
    clearCssVar('--test-var')
    expect(document.documentElement.style.getPropertyValue('--test-var')).toBe('')
  })
})
