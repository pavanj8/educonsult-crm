import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useCreateApplication } from './useCreateApplication'

const mockApplication = {
  id: 1,
  tenant_id: 10,
  student_id: 8,
  university_id: 1,
  program_id: 10,
  stage: 'registered' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('useCreateApplication', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('creates application on success', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockApplication,
    }) as typeof fetch

    const { result } = renderHook(() => useCreateApplication())

    const created = await result.current.createApplication({
      university_id: 1,
      program_id: 10,
    })

    expect(created).toEqual(mockApplication)
    expect(result.current.createError).toBeNull()

    await waitFor(() => {
      expect(result.current.lastCreated).toEqual(mockApplication)
    })
  })

  it('sets createError when creation fails', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'Invalid program' }),
    }) as typeof fetch

    const { result } = renderHook(() => useCreateApplication())

    await expect(
      result.current.createApplication({
        university_id: 1,
        program_id: 10,
      }),
    ).rejects.toMatchObject({ status: 422 })

    await waitFor(() => {
      expect(result.current.createError).toBe('Invalid program')
    })
  })
})
