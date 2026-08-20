import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useStaff } from './useStaff'

const mockStaff = {
  id: 42,
  email: 'counselor@example.test',
  role: 'counselor' as const,
  tenant_id: 10,
  branch_id: 1,
  is_active: true,
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

describe('useStaff', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('creates staff on success', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockStaff,
    }) as typeof fetch

    const { result } = renderHook(() => useStaff())

    const created = await result.current.createStaff({
      email: 'counselor@example.test',
      password: 'secure-password',
      role: 'counselor',
      branch_id: 1,
    })

    expect(created).toEqual(mockStaff)
    expect(result.current.createError).toBeNull()
  })

  it('sets createError when creation fails', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    const { result } = renderHook(() => useStaff())

    await expect(
      result.current.createStaff({
        email: 'counselor@example.test',
        password: 'secure-password',
        role: 'counselor',
        branch_id: 1,
      }),
    ).rejects.toMatchObject({ status: 403 })

    await waitFor(() => {
      expect(result.current.createError).toBe('Insufficient permissions')
    })
  })

  it('deactivates staff and updates list on success', async () => {
    localStorage.setItem('access_token', 'test-token')
    const inactiveStaff = { ...mockStaff, is_active: false }
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [mockStaff],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => inactiveStaff,
      }) as typeof fetch

    const { result } = renderHook(() => useStaff())

    await waitFor(() => {
      expect(result.current.staff).toEqual([mockStaff])
    })

    const updated = await result.current.setStaffActiveStatus(42, false)

    expect(updated).toEqual(inactiveStaff)
    await waitFor(() => {
      expect(result.current.staff).toEqual([inactiveStaff])
    })
    expect(result.current.statusError).toBeNull()
  })

  it('sets statusError when deactivation fails', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [mockStaff],
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Cannot change your own active status' }),
      }) as typeof fetch

    const { result } = renderHook(() => useStaff())

    await waitFor(() => {
      expect(result.current.staff).toEqual([mockStaff])
    })

    await expect(result.current.setStaffActiveStatus(42, false)).rejects.toMatchObject({
      status: 403,
    })

    await waitFor(() => {
      expect(result.current.statusError).toBe('Cannot change your own active status')
    })
  })
})
