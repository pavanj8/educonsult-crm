import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useTenantBrandingSettings } from './useTenantBrandingSettings'

const baseTenant = {
  id: 10,
  name: 'Apex EduConsult',
  slug: 'apex',
  logo_url: null,
  brand_color: '#1f6feb',
  currency: 'USD',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

describe('useTenantBranding', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads the tenant on mount when tenantId is provided', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => baseTenant,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useTenantBrandingSettings(10))

    await waitFor(() => {
      expect(result.current.loadingTenant).toBe(false)
    })

    expect(result.current.tenant).toEqual(baseTenant)
    expect(fetchMock).toHaveBeenCalledWith('/tenants/10', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-token',
      },
    })
  })

  it('sets loadError when the initial GET fails', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Forbidden' }),
    }) as typeof fetch

    const { result } = renderHook(() => useTenantBrandingSettings(10))

    await waitFor(() => {
      expect(result.current.loadingTenant).toBe(false)
    })

    expect(result.current.tenant).toBeNull()
    expect(result.current.loadError).toBe('Forbidden')
  })

  it('updateBranding sets brandingError and throws when tenantId is null', async () => {
    const { result } = renderHook(() => useTenantBrandingSettings(null))

    // Catch the rejection INSIDE act (so React commits the error-state
    // update — an async act callback that rejects rolls its updates back),
    // while still capturing the error to assert the throw.
    let caught: unknown
    await act(async () => {
      caught = await result.current
        .updateBranding({ brand_color: '#ff0000' })
        .catch((err: unknown) => err)
    })

    expect(caught).toBeInstanceOf(Error)
    expect((caught as Error).message).toBe(
      'No tenant is associated with the current account',
    )
    await waitFor(() => {
      expect(result.current.brandingError).toBe(
        'No tenant is associated with the current account',
      )
    })
  })

  it('uploadLogo sets logoError and throws when tenantId is null', async () => {
    const { result } = renderHook(() => useTenantBrandingSettings(null))

    const file = new File(['bytes'], 'logo.png', { type: 'image/png' })
    let caught: unknown
    await act(async () => {
      caught = await result.current.uploadLogo(file).catch((err: unknown) => err)
    })

    expect(caught).toBeInstanceOf(Error)
    expect((caught as Error).message).toBe(
      'No tenant is associated with the current account',
    )
    await waitFor(() => {
      expect(result.current.logoError).toBe(
        'No tenant is associated with the current account',
      )
    })
  })

  it('updateBranding surfaces backend errors and clears on next call', async () => {
    localStorage.setItem('access_token', 'test-token')
    let call = 0
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      call += 1
      if (call === 1) {
        return {
          ok: true,
          status: 200,
          json: async () => baseTenant,
        }
      }
      return {
        ok: false,
        status: 422,
        json: async () => ({ detail: 'Brand color must be a #RRGGBB hex value' }),
      }
    }) as typeof fetch

    const { result } = renderHook(() => useTenantBrandingSettings(10))

    await waitFor(() => {
      expect(result.current.tenant).not.toBeNull()
    })

    await act(async () => {
      try {
        await result.current.updateBranding({ brand_color: 'not-a-color' })
      } catch {
        /* expected */
      }
    })

    await waitFor(() => {
      expect(result.current.brandingError).toBe(
        'Brand color must be a #RRGGBB hex value',
      )
    })

    act(() => {
      result.current.clearBrandingError()
    })
    expect(result.current.brandingError).toBeNull()
  })
})
