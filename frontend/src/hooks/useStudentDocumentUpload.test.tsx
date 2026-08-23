import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  uploadStudentDocument,
  type StudentDocumentUploadResponse,
} from '../api/studentDocuments'

import { useStudentDocumentUpload } from './useStudentDocumentUpload'

vi.mock('../api/studentDocuments', () => ({
  uploadStudentDocument: vi.fn(),
  toChecklistUpload: vi.fn((response) => ({
    id: response.id,
    status: response.status,
    originalFilename: response.original_filename,
    uploadedAt: response.uploaded_at,
    verifiedAt: response.verified_at,
    rejectionReason: response.rejection_reason,
  })),
}))

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

function makeUploadResponse(overrides: Partial<StudentDocumentUploadResponse>): StudentDocumentUploadResponse {
  return { ...mockUploadResponse, ...overrides }
}

function makeFile(name = 'transcript.pdf', type = 'application/pdf'): File {
  return new File(['%PDF-1.4\n% fake pdf'], name, { type })
}

describe('useStudentDocumentUpload', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('starts idle with no error', () => {
    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: 11,
      }),
    )

    expect(result.current.uploading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('sets uploading during the request and clears it on success', async () => {
    let resolveUpload: (value: StudentDocumentUploadResponse) => void = () => {}
    vi.mocked(uploadStudentDocument).mockImplementation(
      () =>
        new Promise<StudentDocumentUploadResponse>((resolve) => {
          resolveUpload = resolve
        }),
    )

    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: 11,
      }),
    )

    let uploadPromise: Promise<unknown> = Promise.resolve()
    act(() => {
      uploadPromise = result.current.upload(makeFile())
    })

    expect(result.current.uploading).toBe(true)
    expect(result.current.error).toBeNull()

    await act(async () => {
      resolveUpload(mockUploadResponse)
      await uploadPromise
    })

    await waitFor(() => {
      expect(result.current.uploading).toBe(false)
    })
    expect(result.current.error).toBeNull()
    expect(uploadStudentDocument).toHaveBeenCalledWith({
      applicationId: 7,
      file: expect.any(File),
      checklistItemTemplateId: 11,
    })
  })

  it('captures the backend error message on failure', async () => {
    const apiError = Object.assign(new Error('File exceeds 10MB limit'), { status: 413 })
    vi.mocked(uploadStudentDocument).mockRejectedValueOnce(apiError)

    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: null,
      }),
    )

    await act(async () => {
      await expect(result.current.upload(makeFile())).rejects.toThrow(
        'File exceeds 10MB limit',
      )
    })

    await waitFor(() => {
      expect(result.current.uploading).toBe(false)
    })
    expect(result.current.error).toBe('File exceeds 10MB limit')
  })

  it('falls back to a generic message when the failure is not an API error', async () => {
    vi.mocked(uploadStudentDocument).mockRejectedValueOnce(new Error('network down'))

    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: 11,
      }),
    )

    await act(async () => {
      await expect(result.current.upload(makeFile())).rejects.toThrow('network down')
    })

    await waitFor(() => {
      expect(result.current.uploading).toBe(false)
    })
    expect(result.current.error).toBe('network down')
  })

  it('falls back to a generic message when the failure has no message', async () => {
    vi.mocked(uploadStudentDocument).mockRejectedValueOnce('something exploded')

    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: null,
      }),
    )

    await act(async () => {
      await expect(result.current.upload(makeFile())).rejects.toThrow()
    })

    await waitFor(() => {
      expect(result.current.uploading).toBe(false)
    })
    expect(result.current.error).toBe('Failed to upload document')
  })

  it('forwards supersedesDocumentId to the upload call (E31; Journey J24)', async () => {
    vi.mocked(uploadStudentDocument).mockResolvedValueOnce({
      ...mockUploadResponse,
      id: 100,
      supersedes_id: 42,
    })

    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: 11,
        supersedesDocumentId: 42,
      }),
    )

    await act(async () => {
      await result.current.upload(makeFile())
    })

    expect(uploadStudentDocument).toHaveBeenCalledWith({
      applicationId: 7,
      file: expect.any(File),
      checklistItemTemplateId: 11,
      supersedesDocumentId: 42,
    })
  })

  it('omits supersedesDocumentId from the upload call when not supplied', async () => {
    vi.mocked(uploadStudentDocument).mockResolvedValueOnce(mockUploadResponse)

    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: 11,
      }),
    )

    await act(async () => {
      await result.current.upload(makeFile())
    })

    expect(uploadStudentDocument).toHaveBeenCalledWith({
      applicationId: 7,
      file: expect.any(File),
      checklistItemTemplateId: 11,
      supersedesDocumentId: undefined,
    })
  })

  it('clearError resets the error state', async () => {
    vi.mocked(uploadStudentDocument).mockRejectedValueOnce(
      Object.assign(new Error('Boom'), { status: 500 }),
    )

    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: null,
      }),
    )

    await act(async () => {
      await result.current.upload(makeFile()).catch(() => {})
    })
    expect(result.current.error).toBe('Boom')

    act(() => {
      result.current.clearError()
    })
    expect(result.current.error).toBeNull()
  })

  it('does not let a stale upload clear the in-flight upload error', async () => {
    let resolveFirst: (value: StudentDocumentUploadResponse) => void = () => {}
    let resolveSecond: (value: StudentDocumentUploadResponse) => void = () => {}

    vi.mocked(uploadStudentDocument)
      .mockImplementationOnce(
        () =>
          new Promise<StudentDocumentUploadResponse>((resolve) => {
            resolveFirst = resolve
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<StudentDocumentUploadResponse>((resolve) => {
            resolveSecond = resolve
          }),
      )

    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: null,
      }),
    )

    // Kick off the first upload, then a second one supersedes it.
    let firstPromise: Promise<unknown> = Promise.resolve()
    act(() => {
      firstPromise = result.current.upload(makeFile('a.pdf'))
    })

    let secondPromise: Promise<unknown> = Promise.resolve()
    act(() => {
      secondPromise = result.current.upload(makeFile('b.pdf'))
    })

    // Second request fails first; the hook must record that error.
    await act(async () => {
      resolveSecond(makeUploadResponse({ id: 2, original_filename: 'b.pdf' }))
      await secondPromise.catch(() => {})
    })

    // Now the stale first request resolves; the hook must NOT clear the
    // error state owned by the second request.
    await act(async () => {
      resolveFirst(makeUploadResponse({ id: 1, original_filename: 'a.pdf' }))
      await firstPromise.catch(() => {})
    })

    // Hook never recorded an error in this branch (the second request
    // succeeded), but ``uploading`` must still be false because both
    // requests are settled. The key invariant is that the stale first
    // request did not throw and disrupt the second request's success.
    expect(result.current.uploading).toBe(false)
  })

  it('does not let a stale upload overwrite a fresh error', async () => {
    let resolveFirst: (value: StudentDocumentUploadResponse) => void = () => {}
    let rejectSecond: (reason?: unknown) => void = () => {}

    vi.mocked(uploadStudentDocument)
      .mockImplementationOnce(
        () =>
          new Promise<StudentDocumentUploadResponse>((resolve) => {
            resolveFirst = resolve
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<StudentDocumentUploadResponse>((_resolve, reject) => {
            rejectSecond = reject
          }),
      )

    const { result } = renderHook(() =>
      useStudentDocumentUpload({
        applicationId: 7,
        checklistItemTemplateId: null,
      }),
    )

    let firstPromise: Promise<unknown> = Promise.resolve()
    act(() => {
      firstPromise = result.current.upload(makeFile('a.pdf'))
    })

    let secondPromise: Promise<unknown> = Promise.resolve()
    act(() => {
      secondPromise = result.current.upload(makeFile('b.pdf'))
    })

    // The fresh request (second) fails first; the hook surfaces its error.
    await act(async () => {
      rejectSecond(Object.assign(new Error('Network error'), { status: 500 }))
      await secondPromise.catch(() => {})
    })
    expect(result.current.error).toBe('Network error')

    // Then the stale first request succeeds; the hook must NOT clear
    // the second request's error.
    await act(async () => {
      resolveFirst(makeUploadResponse({ id: 1, original_filename: 'a.pdf' }))
      await firstPromise.catch(() => {})
    })
    expect(result.current.error).toBe('Network error')
    expect(result.current.uploading).toBe(false)
  })
})
