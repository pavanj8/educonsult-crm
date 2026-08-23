import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createAdminChecklistItemTemplate,
  deleteAdminChecklistItemTemplate,
  fetchAdminChecklistItemTemplates,
  fetchApplicationChecklist,
  updateAdminChecklistItemTemplate,
} from './checklist'

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
        supersedesDocumentId: null,
      },
    },
  ],
}

const mockTemplates = [
  {
    id: 1,
    tenant_id: 10,
    stage: 'registered',
    program_id: null,
    name: 'Passport',
    description: null,
    required: true,
    order_index: 0,
  },
  {
    id: 2,
    tenant_id: 10,
    stage: 'document_verification',
    program_id: 100,
    name: 'Offer letter',
    description: 'Conditional or unconditional offer.',
    required: true,
    order_index: 0,
  },
]

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

describe('checklist template admin CRUD client (E15; Journey J8)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    localStorage.setItem('access_token', 'token-abc')
  })

  it('fetchAdminChecklistItemTemplates lists templates with auth header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockTemplates,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchAdminChecklistItemTemplates()

    expect(result).toEqual(mockTemplates)
    expect(fetchMock).toHaveBeenCalledWith('/checklist-templates', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer token-abc',
      },
    })
  })

  it('fetchAdminChecklistItemTemplates encodes stage and program_id query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    })
    globalThis.fetch = fetchMock as typeof fetch

    await fetchAdminChecklistItemTemplates({
      stage: 'document_verification',
      program_id: 100,
    })

    expect(fetchMock).toHaveBeenCalledWith(
      '/checklist-templates?stage=document_verification&program_id=100',
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer token-abc',
        },
      },
    )
  })

  it('createAdminChecklistItemTemplate posts to the admin endpoint', async () => {
    const created = { ...mockTemplates[0], id: 3 }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => created,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await createAdminChecklistItemTemplate({
      stage: 'registered',
      program_id: null,
      name: 'Passport',
      description: null,
      required: true,
      order_index: 0,
    })

    expect(result).toEqual(created)
    expect(fetchMock).toHaveBeenCalledWith('/checklist-templates', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer token-abc',
      },
      body: JSON.stringify({
        stage: 'registered',
        program_id: null,
        name: 'Passport',
        description: null,
        required: true,
        order_index: 0,
      }),
    })
  })

  it('updateAdminChecklistItemTemplate patches the admin endpoint with id in path', async () => {
    const updated = { ...mockTemplates[0], name: 'Passport scan' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => updated,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await updateAdminChecklistItemTemplate(1, {
      name: 'Passport scan',
    })

    expect(result).toEqual(updated)
    expect(fetchMock).toHaveBeenCalledWith('/checklist-templates/1', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer token-abc',
      },
      body: JSON.stringify({ name: 'Passport scan' }),
    })
  })

  it('deleteAdminChecklistItemTemplate issues DELETE on the admin endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => undefined,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await deleteAdminChecklistItemTemplate(1)

    expect(fetchMock).toHaveBeenCalledWith('/checklist-templates/1', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer token-abc',
      },
    })
  })
})
