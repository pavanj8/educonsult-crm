import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useApplicationChecklist } from './useApplicationChecklist'

const mockResponse = {
  applicationId: 1,
  items: [
    {
      templateId: 10,
      stage: 'registered',
      name: 'Passport',
      description: 'Passport biodata scan',
      required: true,
      orderIndex: 0,
      upload: null,
    },
    {
      templateId: 11,
      stage: 'registered',
      name: 'Transcript',
      description: null,
      required: false,
      orderIndex: 1,
      upload: {
        id: 99,
        status: 'approved',
        originalFilename: 'transcript.pdf',
        uploadedAt: '2026-02-01T10:00:00Z',
        verifiedAt: '2026-02-02T11:00:00Z',
        rejectionReason: null,
      },
    },
  ],
}

describe('useApplicationChecklist', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('loads the checklist when an authenticated application id is provided', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useApplicationChecklist(1))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.items).toEqual(mockResponse.items)
    expect(result.current.error).toBeNull()
    expect(fetchMock).toHaveBeenCalledWith('/applications/1/checklist', expect.any(Object))
  })

  it('skips the fetch when no application id is provided', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useApplicationChecklist(null))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.items).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('skips the fetch when no access token is present', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useApplicationChecklist(1))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.items).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('sets an auth-specific error message on 401', async () => {
    localStorage.setItem('access_token', 'expired-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Not authenticated' }),
    }) as typeof fetch

    const { result } = renderHook(() => useApplicationChecklist(1))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Sign in to view the document checklist')
    expect(result.current.items).toEqual([])
  })

  it('sets an auth-specific error message on 403', async () => {
    localStorage.setItem('access_token', 'token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    const { result } = renderHook(() => useApplicationChecklist(1))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Sign in to view the document checklist')
  })

  it('sets a generic error message on non-auth failures', async () => {
    localStorage.setItem('access_token', 'token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    }) as typeof fetch

    const { result } = renderHook(() => useApplicationChecklist(1))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Failed to load the document checklist')
  })

  it('reloads the checklist when reload is called', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ ...mockResponse, items: [] }),
      })
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useApplicationChecklist(1))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.items).toHaveLength(2)

    await result.current.reload()

    await waitFor(() => {
      expect(result.current.items).toHaveLength(0)
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('refetches when the application id changes', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ applicationId: 2, items: [] }),
      })
    globalThis.fetch = fetchMock as typeof fetch

    const { result, rerender } = renderHook(
      ({ applicationId }: { applicationId: number | null }) =>
        useApplicationChecklist(applicationId),
      { initialProps: { applicationId: 1 as number | null } },
    )

    await waitFor(() => {
      expect(result.current.items).toHaveLength(2)
    })

    rerender({ applicationId: 2 })

    await waitFor(() => {
      expect(result.current.items).toEqual([])
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/applications/1/checklist', expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/applications/2/checklist', expect.any(Object))
  })
})