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
})
