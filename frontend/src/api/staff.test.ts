import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createStaff } from './staff'

const mockStaff = {
  id: 42,
  email: 'counselor@example.test',
  role: 'counselor' as const,
  tenant_id: 10,
  branch_id: 1,
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

describe('staff API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('createStaff posts payload with auth header', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockStaff,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const payload = {
      email: 'counselor@example.test',
      password: 'secure-password',
      role: 'counselor' as const,
      branch_id: 1,
    }
    const result = await createStaff(payload)

    expect(result).toEqual(mockStaff)
    expect(fetchMock).toHaveBeenCalledWith('/staff', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
  })

  it('createStaff surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'A user with this email already exists' }),
    }) as typeof fetch

    await expect(
      createStaff({
        email: 'counselor@example.test',
        password: 'secure-password',
        role: 'counselor',
        branch_id: 1,
      }),
    ).rejects.toMatchObject({
      message: 'A user with this email already exists',
      status: 409,
    })
  })
})
