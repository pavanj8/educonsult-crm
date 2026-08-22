import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('returns null when no user is authenticated', async () => {
    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenant).toBeNull()
    expect(result.current.error).toBeNull()
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('fetches the tenant record for the authenticated user', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTenant,
      }) as typeof fetch

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenant).toEqual(mockTenant)
    expect(result.current.error).toBeNull()
    expect(globalThis.fetch).toHaveBeenCalledWith(
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
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Insufficient permissions' }),
      }) as typeof fetch

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenant).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('silently returns null when the tenant row is missing (404)', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Tenant not found' }),
      }) as typeof fetch

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenant).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('exposes transport errors via the error field but leaves tenant null', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'Tenant service is temporarily unavailable' }),
      }) as typeof fetch

    const { result } = renderHook(() => useTenantBranding(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenant).toBeNull()
    expect(result.current.error).toBe('Tenant service is temporarily unavailable')
  })

  it('reload refetches the current tenant branding on demand', async () => {
    localStorage.setItem('access_token', 'test-token')
    const updated = { ...mockTenant, brand_color: '#FF00FF' }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUserWithTenant,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTenant,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => updated,
      }) as typeof fetch

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
