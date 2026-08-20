import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createBranch, fetchBranches, updateBranch } from './branches'

const mockBranch = {
  id: 1,
  tenant_id: 10,
  name: 'Mumbai HQ',
  city: 'Mumbai',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

describe('branches API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('fetchBranches sends bearer token from storage', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [mockBranch],
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchBranches()

    expect(result).toEqual([mockBranch])
    expect(fetchMock).toHaveBeenCalledWith('/branches', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
  })

  it('fetchBranches surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    await expect(fetchBranches()).rejects.toMatchObject({
      message: 'Insufficient permissions',
      status: 403,
    })
  })

  it('createBranch posts payload with auth header', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockBranch,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const payload = { name: 'Mumbai HQ', city: 'Mumbai' }
    const result = await createBranch(payload)

    expect(result).toEqual(mockBranch)
    expect(fetchMock).toHaveBeenCalledWith('/branches', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
  })

  it('updateBranch patches payload with auth header', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockBranch, name: 'Mumbai Main' }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    const payload = { name: 'Mumbai Main' }
    const result = await updateBranch(1, payload)

    expect(result.name).toBe('Mumbai Main')
    expect(fetchMock).toHaveBeenCalledWith('/branches/1', {
      method: 'PATCH',
      body: JSON.stringify(payload),
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
  })

  it('createBranch surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'Branch name is required' }),
    }) as typeof fetch

    await expect(createBranch({ name: '', city: 'Mumbai' })).rejects.toMatchObject({
      message: 'Branch name is required',
      status: 422,
    })
  })
})
