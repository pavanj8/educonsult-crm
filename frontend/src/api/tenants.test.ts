import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createTenant, fetchTenants } from './tenants'

const mockTenant = {
  id: 1,
  name: 'Apex EduConsult',
  slug: 'apex',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

describe('tenants API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('fetchTenants sends bearer token from storage', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [mockTenant],
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchTenants()

    expect(result).toEqual([mockTenant])
    expect(fetchMock).toHaveBeenCalledWith('/tenants', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
  })

  it('createTenant posts payload with auth header', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockTenant,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const payload = {
      name: 'Apex EduConsult',
      slug: 'apex',
      owner_email: 'owner@apex.test',
    }
    const result = await createTenant(payload)

    expect(result).toEqual(mockTenant)
    expect(fetchMock).toHaveBeenCalledWith('/tenants', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
  })

  it('createTenant surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'A tenant with this slug already exists' }),
    }) as typeof fetch

    await expect(
      createTenant({
        name: 'Apex EduConsult',
        slug: 'apex',
        owner_email: 'owner@apex.test',
      }),
    ).rejects.toMatchObject({
      message: 'A tenant with this slug already exists',
      status: 409,
    })
  })
})
