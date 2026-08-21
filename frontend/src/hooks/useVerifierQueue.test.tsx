import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useVerifierQueue } from './useVerifierQueue'

const mockQueue = {
  items: [
    {
      id: 7,
      tenant_id: 10,
      application_id: 3,
      checklist_item_template_id: 2,
      original_filename: 'passport.pdf',
      content_type: 'application/pdf',
      size_bytes: 1024,
      uploaded_by_user_id: 42,
      uploaded_at: '2026-02-01T10:00:00Z',
      application_stage: 'documents',
      student_id: 42,
      university_id: 1,
      program_id: 10,
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
}

describe('useVerifierQueue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('loads the pending queue on mount when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => mockQueue }) as typeof fetch

    const { result } = renderHook(() => useVerifierQueue())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.documents).toHaveLength(1)
    expect(result.current.total).toBe(1)
    expect(result.current.error).toBeNull()
  })

  it('does not fetch when unauthenticated', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useVerifierQueue())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.documents).toEqual([])
  })

  it('maps a 403 to a permission error', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'nope' }),
    }) as typeof fetch

    const { result } = renderHook(() => useVerifierQueue())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toMatch(/permission/i)
  })
})
