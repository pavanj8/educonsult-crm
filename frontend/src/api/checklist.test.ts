import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchApplicationChecklist } from './checklist'

const mockResponse = {
  applicationId: 1,
  items: [
    {
      templateId: 10,
      stage: 'registered',
      name: 'Passport',
      description: 'A clear scan of your passport biodata page.',
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

describe('fetchApplicationChecklist', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('sends a GET to /applications/{id}/checklist with auth header', async () => {
    localStorage.setItem('access_token', 'token-abc')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchApplicationChecklist({ applicationId: 1 })

    expect(result).toEqual(mockResponse)
    expect(fetchMock).toHaveBeenCalledWith('/applications/1/checklist', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer token-abc',
      },
    })
  })

  it('surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'token-abc')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Application not found' }),
    }) as typeof fetch

    await expect(fetchApplicationChecklist({ applicationId: 999 })).rejects.toMatchObject({
      message: 'Application not found',
      status: 404,
    })
  })

  it('surfaces backend error detail on forbidden', async () => {
    localStorage.setItem('access_token', 'token-abc')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Cannot view checklist for an application outside your branch' }),
    }) as typeof fetch

    await expect(fetchApplicationChecklist({ applicationId: 1 })).rejects.toMatchObject({
      message: 'Cannot view checklist for an application outside your branch',
      status: 403,
    })
  })
})