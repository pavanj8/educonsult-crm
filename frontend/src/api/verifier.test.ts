import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchPendingDocuments } from './verifier'
import { isApiError } from './client'

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

describe('verifier API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('fetchPendingDocuments calls the pending endpoint with the bearer token', async () => {
    localStorage.setItem('access_token', 'stored-token')
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => mockQueue })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchPendingDocuments()

    expect(result).toEqual(mockQueue)
    expect(fetchMock).toHaveBeenCalledWith('/verifier/documents/pending', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-token',
      },
    })
  })

  it('fetchPendingDocuments forwards limit/offset as query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => mockQueue })
    globalThis.fetch = fetchMock as typeof fetch

    await fetchPendingDocuments({ limit: 25, offset: 50 })

    expect(fetchMock).toHaveBeenCalledWith(
      '/verifier/documents/pending?limit=25&offset=50',
      expect.anything(),
    )
  })

  it('fetchPendingDocuments surfaces a 403 as an ApiError with status', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Not authorized' }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    await expect(fetchPendingDocuments()).rejects.toThrow()
    try {
      await fetchPendingDocuments()
    } catch (err) {
      expect(isApiError(err) && err.status).toBe(403)
    }
  })
})

describe('rejectDocument API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('posts the comment to the reject endpoint', async () => {
    localStorage.setItem('access_token', 'stored-token')
    const rejected = { id: 7, status: 'rejected', rejection_reason: 'Not legible' }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => rejected })
    globalThis.fetch = fetchMock as typeof fetch

    const { rejectDocument } = await import('./verifier')
    const result = await rejectDocument(7, 'Not legible')

    expect(result).toEqual(rejected)
    expect(fetchMock).toHaveBeenCalledWith(
      '/verifier/documents/7/reject',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ comment: 'Not legible' }) }),
    )
  })
})
