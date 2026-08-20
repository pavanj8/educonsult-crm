import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useBranches } from './useBranches'

const mockBranches = [
  {
    id: 1,
    tenant_id: 10,
    name: 'Mumbai HQ',
    city: 'Mumbai',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 2,
    tenant_id: 10,
    name: 'Delhi Center',
    city: 'Delhi',
    created_at: '2026-01-20T10:00:00Z',
    updated_at: '2026-01-20T10:00:00Z',
  },
]

describe('useBranches', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('loads branches on mount when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockBranches,
    }) as typeof fetch

    const { result } = renderHook(() => useBranches())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.branches).toHaveLength(2)
    expect(result.current.branches[0]?.name).toBe('Mumbai HQ')
  })

  it('skips fetch when no access token is present', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useBranches())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.branches).toHaveLength(0)
  })

  it('skips fetch when disabled', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useBranches({ enabled: false }))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.branches).toHaveLength(0)
  })

  it('sets permission error on 403', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    const { result } = renderHook(() => useBranches())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('You do not have permission to view branches')
  })

  it('appends created branch to the list on success', async () => {
    localStorage.setItem('access_token', 'test-token')
    const newBranch = {
      id: 3,
      tenant_id: 10,
      name: 'Bangalore Office',
      city: 'Bangalore',
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => newBranch,
      }) as typeof fetch

    const { result } = renderHook(() => useBranches())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await result.current.createBranch({ name: 'Bangalore Office', city: 'Bangalore' })

    await waitFor(() => {
      expect(result.current.branches).toHaveLength(3)
    })

    expect(result.current.branches[2]?.name).toBe('Bangalore Office')
    expect(result.current.createError).toBeNull()
  })

  it('sets createError when creation fails', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: 'Branch name is required' }),
      }) as typeof fetch

    const { result } = renderHook(() => useBranches())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await expect(
      result.current.createBranch({ name: '', city: 'Mumbai' }),
    ).rejects.toMatchObject({ status: 422 })

    await waitFor(() => {
      expect(result.current.createError).toBe('Branch name is required')
    })

    expect(result.current.branches).toHaveLength(2)
  })

  it('updates branch in the list on success', async () => {
    localStorage.setItem('access_token', 'test-token')
    const updatedBranch = {
      ...mockBranches[0],
      name: 'Mumbai Main',
      updated_at: '2026-02-02T10:00:00Z',
    }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => updatedBranch,
      }) as typeof fetch

    const { result } = renderHook(() => useBranches())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await result.current.updateBranch(1, { name: 'Mumbai Main' })

    await waitFor(() => {
      expect(result.current.branches[0]?.name).toBe('Mumbai Main')
    })

    expect(result.current.updateError).toBeNull()
  })

  it('sets updateError when update fails', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Branch not found' }),
      }) as typeof fetch

    const { result } = renderHook(() => useBranches())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await expect(result.current.updateBranch(1, { name: 'Missing' })).rejects.toMatchObject({
      status: 404,
    })

    await waitFor(() => {
      expect(result.current.updateError).toBe('Branch not found')
    })
  })
})
