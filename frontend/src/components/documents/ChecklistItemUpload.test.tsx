import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ChecklistItemUpload from './ChecklistItemUpload'

const uploadStudentDocumentMock = vi.fn()

vi.mock('../../api/studentDocuments', () => ({
  uploadStudentDocument: (...args: unknown[]) => uploadStudentDocumentMock(...args),
  toChecklistUpload: (response: { id: number; status: string; original_filename: string }) => ({
    id: response.id,
    status: response.status,
    originalFilename: response.original_filename,
    uploadedAt: '2026-02-01T10:00:00Z',
    verifiedAt: null,
    rejectionReason: null,
    supersedesDocumentId: null,
  }),
}))

function makeFile(name: string, type: string, sizeBytes = 1024): File {
  const file = new File([new Uint8Array(sizeBytes)], name, { type })
  return file
}

function renderUpload(
  props: Partial<React.ComponentProps<typeof ChecklistItemUpload>> = {},
) {
  const defaultProps: React.ComponentProps<typeof ChecklistItemUpload> = {
    applicationId: 7,
    checklistItemTemplateId: 11,
  }
  return render(<ChecklistItemUpload {...defaultProps} {...props} />)
}

describe('ChecklistItemUpload', () => {
  beforeEach(() => {
    uploadStudentDocumentMock.mockReset()
  })

  it('renders a trigger that opens the file picker', () => {
    renderUpload()
    const trigger = screen.getByTestId('checklist-item-upload-trigger-11')
    expect(trigger).toHaveTextContent('Upload file')
    expect(trigger.tagName).toBe('LABEL')
  })

  it('uploads a valid PDF and calls onUploaded on success', async () => {
    const user = userEvent.setup()
    const onUploaded = vi.fn()
    uploadStudentDocumentMock.mockResolvedValueOnce({
      id: 99,
      tenant_id: 10,
      application_id: 7,
      checklist_item_template_id: 11,
      status: 'pending',
      original_filename: 'transcript.pdf',
      content_type: 'application/pdf',
      size_bytes: 1024,
      storage_path: 'tenants/10/applications/7/abc-transcript.pdf',
      uploaded_by_user_id: 42,
      uploaded_at: '2026-02-01T10:00:00Z',
      verified_at: null,
      rejection_reason: null,
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    })

    renderUpload({ onUploaded })

    const input = screen.getByTestId('checklist-item-upload-input-11')
    const file = makeFile('transcript.pdf', 'application/pdf')
    await user.upload(input, file)

    await waitFor(() => {
      expect(uploadStudentDocumentMock).toHaveBeenCalledWith({
        applicationId: 7,
        file,
        checklistItemTemplateId: 11,
      })
    })
    await waitFor(() => {
      expect(onUploaded).toHaveBeenCalledTimes(1)
    })
    expect(screen.queryByTestId('checklist-item-upload-status-11')).not.toBeInTheDocument()
  })

  it('shows the filename while the upload is in flight', async () => {
    const user = userEvent.setup()
    let resolveUpload: (value: unknown) => void = () => {}
    uploadStudentDocumentMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve
        }),
    )

    renderUpload()

    const input = screen.getByTestId('checklist-item-upload-input-11')
    await user.upload(input, makeFile('passport.pdf', 'application/pdf'))

    expect(await screen.findByTestId('checklist-item-upload-status-11')).toHaveTextContent(
      'Uploading…',
    )
    expect(screen.getByTestId('checklist-item-upload-filename-11')).toHaveTextContent(
      'passport.pdf',
    )

    // Resolve so the test does not leak the pending promise.
    await waitFor(() => {
      resolveUpload({
        id: 1,
        status: 'pending',
        original_filename: 'passport.pdf',
      })
    })
  })

  it('surfaces the backend error on upload failure', async () => {
    const user = userEvent.setup()
    uploadStudentDocumentMock.mockRejectedValueOnce(
      Object.assign(new Error('Document storage is temporarily unavailable'), { status: 503 }),
    )

    renderUpload()

    const input = screen.getByTestId('checklist-item-upload-input-11')
    await user.upload(input, makeFile('x.pdf', 'application/pdf'))

    expect(
      await screen.findByTestId('checklist-item-upload-error-11'),
    ).toHaveTextContent('Document storage is temporarily unavailable')
    expect(screen.getByTestId('checklist-item-upload-filename-11')).toHaveTextContent('x.pdf')
  })

  it('rejects files larger than 10 MB client-side without hitting the API', async () => {
    const user = userEvent.setup()
    renderUpload()

    const input = screen.getByTestId('checklist-item-upload-input-11')
    await user.upload(input, makeFile('huge.pdf', 'application/pdf', 11 * 1024 * 1024))

    expect(
      await screen.findByTestId('checklist-item-upload-error-11'),
    ).toHaveTextContent('too large')
    expect(uploadStudentDocumentMock).not.toHaveBeenCalled()
  })

  it('rejects unsupported file extensions client-side', async () => {
    renderUpload()

    const input = screen.getByTestId('checklist-item-upload-input-11')
    // ``userEvent.upload`` respects the ``accept`` attribute and would
    // refuse to dispatch a change event for a non-allowed extension.
    // ``fireEvent.change`` lets the test simulate the user picking a
    // .txt file directly, which is the case we want to exercise.
    fireEvent.change(input, { target: { files: [makeFile('notes.txt', 'text/plain')] } })

    expect(
      await screen.findByTestId('checklist-item-upload-error-11'),
    ).toHaveTextContent('Only PDF, JPG, PNG, or DOCX files are allowed')
    expect(uploadStudentDocumentMock).not.toHaveBeenCalled()
  })

  it('disables the input while uploading', async () => {
    const user = userEvent.setup()
    let resolveUpload: (value: unknown) => void = () => {}
    uploadStudentDocumentMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve
        }),
    )

    renderUpload()

    const input = screen.getByTestId('checklist-item-upload-input-11')
    await user.upload(input, makeFile('a.pdf', 'application/pdf'))

    await waitFor(() => {
      expect(input).toBeDisabled()
    })

    resolveUpload({ id: 1, status: 'pending', original_filename: 'a.pdf' })
  })

  it('disables the input when the disabled prop is set', () => {
    renderUpload({ disabled: true })
    expect(screen.getByTestId('checklist-item-upload-input-11')).toBeDisabled()
  })

  it('uses the "adhoc" key for ad-hoc uploads (null template id)', () => {
    renderUpload({ checklistItemTemplateId: null })
    expect(screen.getByTestId('checklist-item-upload-input-adhoc')).toBeInTheDocument()
    expect(screen.getByTestId('checklist-item-upload-trigger-adhoc')).toBeInTheDocument()
  })

  it('clears the displayed error when a new file is picked', async () => {
    const user = userEvent.setup()
    uploadStudentDocumentMock
      .mockRejectedValueOnce(
        Object.assign(new Error('Storage outage'), { status: 503 }),
      )
      .mockResolvedValueOnce({
        id: 2,
        tenant_id: 10,
        application_id: 7,
        checklist_item_template_id: 11,
        status: 'pending',
        original_filename: 'b.pdf',
        content_type: 'application/pdf',
        size_bytes: 1024,
        storage_path: 'x',
        uploaded_by_user_id: 42,
        uploaded_at: '2026-02-01T10:00:00Z',
        verified_at: null,
        rejection_reason: null,
        created_at: '2026-02-01T10:00:00Z',
        updated_at: '2026-02-01T10:00:00Z',
      })

    renderUpload()

    const input = screen.getByTestId('checklist-item-upload-input-11')
    await user.upload(input, makeFile('a.pdf', 'application/pdf'))
    expect(
      await screen.findByTestId('checklist-item-upload-error-11'),
    ).toHaveTextContent('Storage outage')

    await user.upload(input, makeFile('b.pdf', 'application/pdf'))

    await waitFor(() => {
      expect(screen.queryByTestId('checklist-item-upload-error-11')).not.toBeInTheDocument()
    })
  })
})
