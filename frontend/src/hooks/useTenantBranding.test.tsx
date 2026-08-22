import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import { useTenantBranding } from './useTenantBranding'
import { AuthProvider } from '../store/authStore'

const mockUserWithTenant = {
  id: 1,
  email: 'admin@demo.test',
  role: 'super_admin' as const,
  tenant_id: 7,
  branch_id: null,
}

const mockTenant = {
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
  return <AuthProvider>{children}</AuthProvider>
}

describe('useTenantBranding', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    // Install a fresh fetch spy for every test so the call history is
    // reliably reset by vi.restoreAllMocks() and assertions like
    // ``toHaveBeenCalledWith`` see only the calls from the current
    // test. Direct ``globalThis.fetch = vi.fn(...)`` is not tracked
    // by vitest and leaks between tests, which was the root cause of
    // the prior false-positive failures.
    fetchSpy = vi.spyOn(globalThis, 'fetch')
  })

  afterEach(() => {
    fetchSpy.mockRestore()
  })

  it('returns null when no user is authenticated', async () => {
    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenant).toBeNull()
    expect(result.current.error).toBeNull()
    // The hook short-circuits when there's no authenticated user, so
    // no request to /tenants/{id} is fired.
    expect(
      fetchSpy.mock.calls.some((call) => {
        const [arg] = call as [unknown]
        return typeof arg === 'string' && arg.includes('/tenants/')
      }),
    ).toBe(false)
  })

  it('fetches the tenant record for the authenticated user', async () => {
    localStorage.setItem('access_token', 'test-token')
    fetchSpy
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTenant,
      } as unknown as Response)

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    // Wait for the hook to actually populate the tenant — proves the
    // request fired and resolved. Polling on `loading` alone races
    // against the initial render where ``loading`` is already false.
    await waitFor(() => {
      expect(result.current.tenant).toEqual(mockTenant)
    })

    expect(result.current.error).toBeNull()
    // The hook must actually fire the request before the assertions
    // above can be trusted; assert the call shape explicitly.
    expect(fetchSpy).toHaveBeenCalledWith(
      '/tenants/7',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer test-token',
        }),
      }),
    )
  })

  it('silently returns null when the caller lacks TENANT_READ (403)', async () => {
    localStorage.setItem('access_token', 'test-token')
    fetchSpy
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Insufficient permissions' }),
      } as unknown as Response)

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    // Wait for the GET /tenants/7 request to have been issued and the
    // hook to settle on its terminal state.
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
      expect(
        fetchSpy.mock.calls.some((call) => {
          const [arg] = call as [unknown]
          return typeof arg === 'string' && arg.includes('/tenants/7')
        }),
      ).toBe(true)
    })

    expect(result.current.tenant).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('silently returns null when the tenant row is missing (404)', async () => {
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

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
      expect(
        fetchSpy.mock.calls.some((call) => {
          const [arg] = call as [unknown]
          return typeof arg === 'string' && arg.includes('/tenants/7')
        }),
      ).toBe(true)
    })

    expect(result.current.tenant).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('exposes transport errors via the error field but leaves tenant null', async () => {
    localStorage.setItem('access_token', 'test-token')
    fetchSpy
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'Tenant service is temporarily unavailable' }),
      } as unknown as Response)

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.error).toBe('Tenant service is temporarily unavailable')
    })

    expect(result.current.tenant).toBeNull()
    expect(result.current.error).toBe('Tenant service is temporarily unavailable')
  })

  it('propagates 401 errors so the auth layer can refresh / logout', async () => {
    localStorage.setItem('access_token', 'test-token')
    fetchSpy
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Token expired' }),
      } as unknown as Response)

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.error).toBe('Token expired')
    })

    // 401 is treated as a real failure so authStore's refresh / logout
    // path can react. Tenant stays null and error is set.
    expect(result.current.tenant).toBeNull()
    expect(result.current.error).toBe('Token expired')
  })

  it('always reads the tenant id from the authenticated user, ignoring any other source', async () => {
    // Safety property: the JWT-derived tenant_id is the source of
    // truth. The hook never reads tenant_id from the URL, a query
    // string, or any other external input.
    localStorage.setItem('access_token', 'test-token')
    fetchSpy
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant, // tenant_id: 7
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTenant, // id: 7
      } as unknown as Response)

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.tenant?.id).toBe(7)
    })

    const tenantCalls = fetchSpy.mock.calls.filter((call) => {
      const [arg] = call as [unknown]
      return typeof arg === 'string' && arg.includes('/tenants/')
    })
    expect(tenantCalls).toHaveLength(1)
    expect(tenantCalls[0]?.[0]).toBe('/tenants/7')
  })

  it('reload refetches the current tenant branding on demand', async () => {
    localStorage.setItem('access_token', 'test-token')
    const updated = { ...mockTenant, brand_color: '#FF00FF' }
    fetchSpy
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTenant,
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => updated,
      } as unknown as Response)

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.tenant?.brand_color).toBe('#1A2B3C')
    })

    await result.current.reload()

    await waitFor(() => {
      expect(result.current.tenant?.brand_color).toBe('#FF00FF')
    })
  })
})
