import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createStaff,
  fetchStaff,
  fetchStaffById,
  updateStaff,
} from './staff'

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

  it('fetchStaff loads staff list with auth header', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [mockStaff],
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchStaff()

    expect(result).toEqual([mockStaff])
    expect(fetchMock).toHaveBeenCalledWith('/staff', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
  })

  it('fetchStaffById loads a staff member', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStaff,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchStaffById(42)

    expect(result).toEqual(mockStaff)
    expect(fetchMock).toHaveBeenCalledWith('/staff/42', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
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

  it('updateStaff patches role and branch', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const updatedStaff = { ...mockStaff, role: 'receptionist' as const, branch_id: 2 }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => updatedStaff,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const payload = { role: 'receptionist' as const, branch_id: 2 }
    const result = await updateStaff(42, payload)

    expect(result).toEqual(updatedStaff)
    expect(fetchMock).toHaveBeenCalledWith('/staff/42', {
      method: 'PATCH',
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
