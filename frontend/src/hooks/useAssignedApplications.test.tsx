import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAssignedApplications } from './useAssignedApplications'

const mockApps = [
  { id: 1, tenant_id: 10, branch_id: 1, student_id: 42, assigned_counselor_id: 7, university_id: 1, program_id: 2, stage: 'registered', created_at: '2026-02-01T10:00:00Z', updated_at: '2026-02-01T10:00:00Z' },
]

describe('useAssignedApplications', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('loads the assigned queue when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => mockApps }) as typeof fetch
    const { result } = renderHook(() => useAssignedApplications())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.applications).toHaveLength(1)
    expect(result.current.error).toBeNull()
  })

  it('maps a 403 to a permission error', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({ detail: 'no' }) }) as typeof fetch
    const { result } = renderHook(() => useAssignedApplications())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toMatch(/permission/i)
  })
})
