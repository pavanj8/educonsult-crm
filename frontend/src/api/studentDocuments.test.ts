import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  toChecklistUpload,
  uploadStudentDocument,
  type StudentDocumentUploadResponse,
} from './studentDocuments'

const mockUploadResponse: StudentDocumentUploadResponse = {
  id: 99,
  tenant_id: 10,
  application_id: 7,
  checklist_item_template_id: 11,
  status: 'pending',
  original_filename: 'transcript.pdf',
  content_type: 'application/pdf',
  size_bytes: 14,
  storage_path: 'tenants/10/applications/7/abc-transcript.pdf',
  uploaded_by_user_id: 42,
  uploaded_at: '2026-02-01T10:00:00Z',
  verified_at: null,
  rejection_reason: null,
  supersedes_id: null,
  created_at: '2026-02-01T10:00:00Z',
  updated_at: '2026-02-01T10:00:00Z',
}

function makeFile(name = 'transcript.pdf', type = 'application/pdf'): File {
  return new File(['%PDF-1.4\n% fake pdf'], name, { type })
}

describe('uploadStudentDocument', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('posts the file as multipart/form-data with the auth header', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockUploadResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const file = makeFile()
    const result = await uploadStudentDocument({ applicationId: 7, file })

    expect(result).toEqual(mockUploadResponse)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [calledUrl, calledInit] = fetchMock.mock.calls[0]!
    expect(calledUrl).toBe('/applications/7/documents')
    expect(calledInit.method).toBe('POST')
    // FormData carries the file under the contract key used by the
    // backend (sibling ticket #175).
    const body = calledInit.body as FormData
    expect(body).toBeInstanceOf(FormData)
    const appendedFile = body.get('file')
    expect(appendedFile).toBe(file)
    // The optional FK is omitted when not supplied (ad-hoc uploads).
    expect(body.get('checklist_item_template_id')).toBeNull()
    // The default JSON Content-Type must NOT be set for multipart —
    // the browser is responsible for the multipart boundary.
    const headers = calledInit.headers as Record<string, string>
    expect(headers['Content-Type']).toBeUndefined()
    expect(headers['Authorization']).toBe('Bearer test-token')
  })

  it('appends checklist_item_template_id when supplied', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockUploadResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await uploadStudentDocument({
      applicationId: 7,
      file: makeFile(),
      checklistItemTemplateId: 11,
    })

    const body = fetchMock.mock.calls[0]![1]!.body as FormData
    expect(body.get('checklist_item_template_id')).toBe('11')
  })

  it('omits checklist_item_template_id when explicitly null', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockUploadResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await uploadStudentDocument({
      applicationId: 7,
      file: makeFile(),
      checklistItemTemplateId: null,
    })

    const body = fetchMock.mock.calls[0]![1]!.body as FormData
    expect(body.has('checklist_item_template_id')).toBe(false)
  })

  it('appends supersedes_document_id when supplied (E31; Journey J24)', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockUploadResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await uploadStudentDocument({
      applicationId: 7,
      file: makeFile(),
      supersedesDocumentId: 42,
    })

    const body = fetchMock.mock.calls[0]![1]!.body as FormData
    expect(body.get('supersedes_document_id')).toBe('42')
  })

  it('omits supersedes_document_id when explicitly null (initial-upload path)', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockUploadResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await uploadStudentDocument({
      applicationId: 7,
      file: makeFile(),
      supersedesDocumentId: null,
    })

    const body = fetchMock.mock.calls[0]![1]!.body as FormData
    expect(body.has('supersedes_document_id')).toBe(false)
  })

  it('omits supersedes_document_id when not supplied (initial-upload path)', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockUploadResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await uploadStudentDocument({ applicationId: 7, file: makeFile() })

    const body = fetchMock.mock.calls[0]![1]!.body as FormData
    expect(body.has('supersedes_document_id')).toBe(false)
  })

  it('surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'Invalid checklist_item_template_id' }),
    }) as typeof fetch

    await expect(
      uploadStudentDocument({
        applicationId: 7,
        file: makeFile(),
        checklistItemTemplateId: 999,
      }),
    ).rejects.toMatchObject({
      message: 'Invalid checklist_item_template_id',
      status: 422,
    })
  })

  it('surfaces backend error detail on storage outage', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Document storage is temporarily unavailable' }),
    }) as typeof fetch

    await expect(
      uploadStudentDocument({ applicationId: 7, file: makeFile() }),
    ).rejects.toMatchObject({
      message: 'Document storage is temporarily unavailable',
      status: 503,
    })
  })

  it('surfaces backend error detail on missing file', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: "Missing 'file' form field" }),
    }) as typeof fetch

    await expect(
      uploadStudentDocument({ applicationId: 7, file: makeFile() }),
    ).rejects.toMatchObject({
      message: "Missing 'file' form field",
      status: 400,
    })
  })
})

describe('toChecklistUpload', () => {
  it('projects a StudentDocumentUploadResponse to the ChecklistUpload shape', () => {
    expect(toChecklistUpload(mockUploadResponse)).toEqual({
      id: 99,
      status: 'pending',
      originalFilename: 'transcript.pdf',
      uploadedAt: '2026-02-01T10:00:00Z',
      verifiedAt: null,
      rejectionReason: null,
      supersedesDocumentId: null,
    })
  })

  it('preserves rejection reason for rejected uploads', () => {
    const rejected: StudentDocumentUploadResponse = {
      ...mockUploadResponse,
      status: 'rejected',
      verified_at: '2026-02-02T11:00:00Z',
      rejection_reason: 'Please re-upload with a scanned signature.',
    }
    expect(toChecklistUpload(rejected)).toEqual({
      id: 99,
      status: 'rejected',
      originalFilename: 'transcript.pdf',
      uploadedAt: '2026-02-01T10:00:00Z',
      verifiedAt: '2026-02-02T11:00:00Z',
      rejectionReason: 'Please re-upload with a scanned signature.',
      supersedesDocumentId: null,
    })
  })

  it('propagates supersedes_id on the projected shape (E31; Journey J24)', () => {
    const reupload: StudentDocumentUploadResponse = {
      ...mockUploadResponse,
      id: 100,
      supersedes_id: 99,
    }
    expect(toChecklistUpload(reupload).supersedesDocumentId).toBe(99)
  })
})
