import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useStaff } from './useStaff'

const mockStaff = {
  id: 42,
  email: 'counselor@example.test',
  role: 'counselor' as const,
  tenant_id: 10,
  branch_id: 1,
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
})
