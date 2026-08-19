import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useTenants } from './useTenants'

const mockTenants = [
  {
    id: 1,
    name: 'Apex EduConsult',
    slug: 'apex',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
]

describe('useTenants', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('loads tenants on mount when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockTenants,
    }) as typeof fetch

    const { result } = renderHook(() => useTenants())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenants).toHaveLength(1)
    expect(result.current.tenants[0]?.name).toBe('Apex EduConsult')
  })

  it('skips fetch when no access token is present', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useTenants())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.tenants).toHaveLength(0)
  })

  it('sets permission error on 403', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    const { result } = renderHook(() => useTenants())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('You do not have permission to view tenants')
  })

  it('appends created tenant to the list on success', async () => {
    localStorage.setItem('access_token', 'test-token')
    const newTenant = {
      id: 2,
      name: 'Bright Future',
      slug: 'bright-future',
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTenants,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => newTenant,
      }) as typeof fetch

    const { result } = renderHook(() => useTenants())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await result.current.createTenant({
      name: 'Bright Future',
      slug: 'bright-future',
      owner_email: 'owner@bright.test',
    })

    await waitFor(() => {
      expect(result.current.tenants).toHaveLength(2)
    })

    expect(result.current.tenants[1]?.slug).toBe('bright-future')
    expect(result.current.createError).toBeNull()
  })

  it('sets createError when creation fails', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTenants,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({ detail: 'A tenant with this slug already exists' }),
      }) as typeof fetch

    const { result } = renderHook(() => useTenants())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await expect(
      result.current.createTenant({
        name: 'Apex EduConsult',
        slug: 'apex',
        owner_email: 'owner@apex.test',
      }),
    ).rejects.toMatchObject({ status: 409 })

    await waitFor(() => {
      expect(result.current.createError).toBe('A tenant with this slug already exists')
    })

    expect(result.current.tenants).toHaveLength(1)
  })
})
