import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import { useDisplayCurrency } from './useDisplayCurrency'
import { AuthProvider } from '../../store/authStore'
import { DEFAULT_CURRENCY_CODE } from './formatCurrencyAmount'

const mockUserWithTenant = {
  id: 1,
  email: 'admin@demo.test',
  role: 'super_admin' as const,
  tenant_id: 7,
  branch_id: null,
}

function makeTenant(currency: string | null) {
  return {
    id: 7,
    name: 'Apex EduConsult',
    slug: 'apex',
    logo_url: 'https://cdn.example.test/apex/logo.png',
    brand_color: '#1A2B3C',
    currency,
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  }
}

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

/**
 * Mock response that authenticates the user via ``GET /auth/me`` and
 * then returns the supplied tenant payload for ``GET /tenants/{id}``.
 */
function installFetchSpy(
  fetchSpy: ReturnType<typeof vi.spyOn>,
  tenantPayload: unknown,
) {
  fetchSpy
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUserWithTenant,
    } as unknown as Response)
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => tenantPayload,
    } as unknown as Response)
}

describe('useDisplayCurrency', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    fetchSpy = vi.spyOn(globalThis, 'fetch')
  })

  afterEach(() => {
    fetchSpy.mockRestore()
  })

  it('returns the default code as a fallback when no user is authenticated', () => {
    const { result } = renderHook(() => useDisplayCurrency(), { wrapper })

    expect(result.current.code).toBe(DEFAULT_CURRENCY_CODE)
    expect(result.current.source).toBe('fallback')
    expect(result.current.loading).toBe(false)
  })

  it('returns the default code as a fallback while the tenant record is loading', async () => {
    localStorage.setItem('access_token', 'test-token')
    // First call resolves the user payload immediately; the tenant
    // fetch is left pending so we can observe the loading state.
    fetchSpy
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      } as unknown as Response)
      .mockReturnValueOnce(new Promise(() => {}) as unknown as Promise<Response>)

    const { result } = renderHook(() => useDisplayCurrency(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(true)
    })

    expect(result.current.code).toBe(DEFAULT_CURRENCY_CODE)
    expect(result.current.source).toBe('fallback')
  })

  it('uses the tenant currency when the record carries a curated code', async () => {
    localStorage.setItem('access_token', 'test-token')
    installFetchSpy(fetchSpy, makeTenant('USD'))

    const { result } = renderHook(() => useDisplayCurrency(), { wrapper })

    await waitFor(() => {
      expect(result.current.code).toBe('USD')
      expect(result.current.source).toBe('tenant')
    })

    expect(result.current.loading).toBe(false)
  })

  it('normalises mixed-case currency codes returned by the server', async () => {
    localStorage.setItem('access_token', 'test-token')
    installFetchSpy(fetchSpy, makeTenant('eur'))

    const { result } = renderHook(() => useDisplayCurrency(), { wrapper })

    await waitFor(() => {
      expect(result.current.code).toBe('EUR')
    })
  })

  it('falls back when the server returns a code outside the curated set', async () => {
    // A non-curated but syntactically valid code (e.g. one written
    // by a custom admin tool) should not crash the UI; we surface
    // the default instead.
    localStorage.setItem('access_token', 'test-token')
    installFetchSpy(fetchSpy, makeTenant('JPY'))

    const { result } = renderHook(() => useDisplayCurrency(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.code).toBe(DEFAULT_CURRENCY_CODE)
    expect(result.current.source).toBe('fallback')
  })

  it('falls back when the server returns a syntactically invalid code', async () => {
    localStorage.setItem('access_token', 'test-token')
    installFetchSpy(fetchSpy, makeTenant('us'))

    const { result } = renderHook(() => useDisplayCurrency(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.code).toBe(DEFAULT_CURRENCY_CODE)
    expect(result.current.source).toBe('fallback')
  })

  it('falls back when the server returns a null currency field', async () => {
    localStorage.setItem('access_token', 'test-token')
    installFetchSpy(fetchSpy, makeTenant(null))

    const { result } = renderHook(() => useDisplayCurrency(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.code).toBe(DEFAULT_CURRENCY_CODE)
    expect(result.current.source).toBe('fallback')
  })

  it('falls back when the tenant row is missing (404)', async () => {
    localStorage.setItem('access_token', 'test-token')
    fetchSpy
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Tenant not found' }),
      } as unknown as Response)

    const { result } = renderHook(() => useDisplayCurrency(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.code).toBe(DEFAULT_CURRENCY_CODE)
    expect(result.current.source).toBe('fallback')
  })
})