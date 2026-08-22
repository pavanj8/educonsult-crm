import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import {
  BrandingProvider,
  BRAND_COLOR_VAR,
  BRAND_COLOR_CONTRAST_VAR,
  useBranding,
} from './brandingStore'
import {
  parseHexColor,
  pickContrastColor,
} from './brandingColor'
import { AuthProvider } from './authStore'

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
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    document.documentElement.removeAttribute('style')
    fetchSpy = vi.spyOn(globalThis, 'fetch')
  })

  afterEach(() => {
    fetchSpy.mockRestore()
    document.documentElement.removeAttribute('style')
  })

  function setupFetchMock(
    routes: Record<string, { ok: boolean; status: number; json: () => Promise<unknown> }>,
  ): void {
    fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      for (const [prefix, response] of Object.entries(routes)) {
        if (url.includes(prefix)) {
          return {
            ok: response.ok,
            status: response.status,
            json: response.json,
          } as Response
        }
      }
      throw new Error(`Unexpected fetch in test: ${url}`)
    })
  }

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
    setupFetchMock({
      '/auth/me': {
        ok: true,
        status: 200,
        json: async () => superAdminUser,
      },
      '/tenants/7': {
        ok: true,
        status: 200,
        json: async () => brandedTenant,
      },
    })

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
  })

  it('clears CSS variables when branding becomes unavailable (logout)', async () => {
    localStorage.setItem('access_token', 'test-token')
    let tenantCalls = 0
    fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.includes('/auth/me')) {
        return {
          ok: true,
          status: 200,
          json: async () => superAdminUser,
        } as Response
      }
      if (url.includes('/tenants/7')) {
        tenantCalls += 1
        if (tenantCalls === 1) {
          return {
            ok: true,
            status: 200,
            json: async () => brandedTenant,
          } as Response
        }
        return {
          ok: false,
          status: 403,
          json: async () => ({ detail: 'Insufficient permissions' }),
        } as Response
      }
      throw new Error(`Unexpected fetch in test: ${url}`)
    })

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
  })
})

describe('brandingColor helpers', () => {
  it('picks white text on dark backgrounds', () => {
    expect(pickContrastColor('#000000')).toBe('#ffffff')
    expect(pickContrastColor('#1A2B3C')).toBe('#ffffff')
    expect(pickContrastColor('#2563EB')).toBe('#ffffff')
    expect(pickContrastColor('#DC2626')).toBe('#ffffff')
  })

  it('picks dark text on medium and light backgrounds', () => {
    expect(pickContrastColor('#FFFFFF')).toBe('#111827')
    expect(pickContrastColor('#FAFAFA')).toBe('#111827')
    expect(pickContrastColor('#FFD700')).toBe('#111827')
    // #10B981 (emerald) and #3B82F6 (blue-500) clear WCAG AA only
    // when paired with dark text — the picker uses the
    // luminance < 0.2 -> white threshold to make that decision.
    expect(pickContrastColor('#10B981')).toBe('#111827')
    expect(pickContrastColor('#3B82F6')).toBe('#111827')
  })

  it('falls back to white contrast for malformed inputs', () => {
    expect(pickContrastColor('not-a-color')).toBe('#ffffff')
    expect(pickContrastColor('#FFF')).toBe('#ffffff')
  })

  it('parses valid hex colors', () => {
    expect(parseHexColor('#1A2B3C')).toEqual([26, 43, 60])
    expect(parseHexColor('#abcdef')).toEqual([0xab, 0xcd, 0xef])
  })

  it('rejects malformed hex colors', () => {
    expect(parseHexColor('1A2B3C')).toBeNull()
    expect(parseHexColor('#FFF')).toBeNull()
    expect(parseHexColor('#ZZZZZZ')).toBeNull()
  })

  it('meets WCAG AA (>= 4.5:1) for the most common brand-color range', () => {
    // The token is chosen via a luminance threshold; verify the most
    // common brand-color picks (dark/saturated, light/neutral) clear
    // the 4.5:1 contrast bar against the chosen token. Near-grey
    // mid-tones (e.g. #7C7C7C) are documented as boundary cases the
    // tenant can avoid by choosing a more saturated brand color.
    const wcag = (a: string, b: string): number => {
      const lum = (hex: string): number => {
        const c = parseHexColor(hex)
        if (c === null) {
          return 0
        }
        const [r, g, b] = c
        const lin = (v: number): number => {
          const x = v / 255
          return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
        }
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
      }
      const la = lum(a)
      const lb = lum(b)
      const lighter = Math.max(la, lb)
      const darker = Math.min(la, lb)
      return (lighter + 0.05) / (darker + 0.05)
    }
    const samples = [
      '#1A2B3C',
      '#2563EB',
      '#000000',
      '#FFFFFF',
      '#FAFAFA',
      '#FFD700',
      '#3B82F6',
      '#DC2626',
      '#10B981',
    ]
    for (const bg of samples) {
      const token = pickContrastColor(bg)
      const ratio = wcag(bg, token)
      expect(ratio).toBeGreaterThanOrEqual(4.5)
    }
  })
})
