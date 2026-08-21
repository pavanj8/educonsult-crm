import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useApplications } from './useApplications'

const mockApplications = [
  {
    id: 1,
    tenant_id: 10,
    student_id: 42,
    university_id: 1,
    program_id: 10,
    stage: 'registered' as const,
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 2,
    tenant_id: 10,
    student_id: 42,
    university_id: 2,
    program_id: 20,
    stage: 'counseling' as const,
    created_at: '2026-01-20T10:00:00Z',
    updated_at: '2026-01-21T10:00:00Z',
  },
]

describe('useApplications', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('loads applications on mount when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockApplications,
    }) as typeof fetch

    const { result } = renderHook(() => useApplications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.applications).toHaveLength(2)
    expect(result.current.applications[0]?.stage).toBe('registered')
    expect(result.current.applications[1]?.stage).toBe('counseling')
  })

  it('skips fetch when no access token is present', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useApplications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.applications).toHaveLength(0)
  })

  it('sets permission error on 403', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    const { result } = renderHook(() => useApplications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('You do not have permission to view applications')
  })

  it('sets generic error on server failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal server error' }),
    }) as typeof fetch

    const { result } = renderHook(() => useApplications())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Failed to load applications')
  })
})
