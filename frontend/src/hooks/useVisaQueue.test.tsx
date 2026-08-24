import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useVisaQueue } from './useVisaQueue'

const mockQueue = {
  items: [
    {
      id: 101,
      tenant_id: 10,
      branch_id: 1,
      student_id: 42,
      assigned_counselor_id: 7,
      university_id: 5,
      program_id: 11,
      stage: 'visa_processing',
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-02T10:00:00Z',
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
}

describe('useVisaQueue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('loads the queue on mount when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockQueue,
    }) as typeof fetch

    const { result } = renderHook(() => useVisaQueue())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.applications).toHaveLength(1)
    expect(result.current.total).toBe(1)
    expect(result.current.error).toBeNull()
  })

  it('does not fetch when unauthenticated', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useVisaQueue())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.applications).toEqual([])
  })

  it('maps a 403 to a permission error', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'nope' }),
    }) as typeof fetch

    const { result } = renderHook(() => useVisaQueue())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toMatch(/permission/i)
  })

  it('surfaces the backend detail message on 5xx errors', async () => {
    // The visa queue router (#191) translates a database outage into
    // a 503 with detail "Visa queue is temporarily unavailable"; the
    // hook must propagate that detail to the UI so the operator can
    // distinguish a transient backend issue from a generic failure.
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Visa queue is temporarily unavailable' }),
    }) as typeof fetch

    const { result } = renderHook(() => useVisaQueue())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('Visa queue is temporarily unavailable')
  })

  it('starts with an empty outcomes map and remembers recorded outcomes', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockQueue,
    }) as typeof fetch

    const { result } = renderHook(() => useVisaQueue())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.outcomes).toEqual({})

    const outcome = {
      id: 11,
      tenant_id: 10,
      application_id: 101,
      status: 'approved',
      outcome_date: null,
      notes: 'OK',
      created_at: '2026-02-03T10:00:00Z',
      updated_at: '2026-02-03T10:00:00Z',
    }

    act(() => {
      result.current.rememberOutcome(outcome)
    })

    expect(result.current.outcomes).toEqual({ 101: outcome })
  })
})
