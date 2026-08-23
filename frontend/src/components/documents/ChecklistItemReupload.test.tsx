import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ChecklistItemReupload from './ChecklistItemReupload'

const uploadStudentDocumentMock = vi.fn()

vi.mock('../../api/studentDocuments', () => ({
  uploadStudentDocument: (...args: unknown[]) => uploadStudentDocumentMock(...args),
  toChecklistUpload: (response: {
    id: number
    status: string
    original_filename: string
    supersedes_id: number | null
  }) => ({
    id: response.id,
    status: response.status,
    originalFilename: response.original_filename,
    uploadedAt: '2026-02-01T10:00:00Z',
    verifiedAt: null,
    rejectionReason: null,
    supersedesDocumentId: response.supersedes_id,
  }),
}))

function makeFile(name: string, type: string, sizeBytes = 1024): File {
  return new File([new Uint8Array(sizeBytes)], name, { type })
}

function renderReupload(
  props: Partial<React.ComponentProps<typeof ChecklistItemReupload>> = {},
) {
  const defaultProps: React.ComponentProps<typeof ChecklistItemReupload> = {
    applicationId: 7,
    checklistItemTemplateId: 11,
    supersedesDocumentId: 42,
  }
  return render(<ChecklistItemReupload {...defaultProps} {...props} />)
}

describe('ChecklistItemReupload', () => {
  beforeEach(() => {
    uploadStudentDocumentMock.mockReset()
  })

  it('renders a "Re-upload file" trigger that opens the file picker', () => {
    renderReupload()

    const trigger = screen.getByTestId('checklist-item-reupload-11-trigger')
    expect(trigger).toHaveTextContent('Re-upload file')
    expect(trigger.tagName).toBe('LABEL')

    const container = screen.getByTestId('checklist-item-reupload-11')
    expect(container).toHaveTextContent('Upload a corrected version to replace the rejected file.')
  })

  it('forwards supersedesDocumentId to the upload call (E31; Journey J24)', async () => {
    const user = userEvent.setup()
    const onUploaded = vi.fn()
    uploadStudentDocumentMock.mockResolvedValueOnce({
      id: 100,
      tenant_id: 10,
      application_id: 7,
      checklist_item_template_id: 11,
      status: 'pending',
      original_filename: 'passport-v2.pdf',
      content_type: 'application/pdf',
      size_bytes: 1024,
      storage_path: 'tenants/10/applications/7/abc.pdf',
      uploaded_by_user_id: 42,
      uploaded_at: '2026-02-01T10:00:00Z',
      verified_at: null,
      rejection_reason: null,
      supersedes_id: 42,
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    })

    renderReupload({ onUploaded })

    const input = screen.getByTestId('checklist-item-reupload-11-input')
    const file = makeFile('passport-v2.pdf', 'application/pdf')
    await user.upload(input, file)

    await waitFor(() => {
      expect(uploadStudentDocumentMock).toHaveBeenCalledWith({
        applicationId: 7,
        file,
        checklistItemTemplateId: 11,
        supersedesDocumentId: 42,
      })
    })
    await waitFor(() => {
      expect(onUploaded).toHaveBeenCalledTimes(1)
    })
  })

  it('calls onUploaded after a successful re-upload so the parent can refresh', async () => {
    const user = userEvent.setup()
    const onUploaded = vi.fn()
    uploadStudentDocumentMock.mockResolvedValueOnce({
      id: 101,
      tenant_id: 10,
      application_id: 7,
      checklist_item_template_id: null,
      status: 'pending',
      original_filename: 'sop-v2.pdf',
      content_type: 'application/pdf',
      size_bytes: 1024,
      storage_path: 'tenants/10/applications/7/xyz.pdf',
      uploaded_by_user_id: 42,
      uploaded_at: '2026-02-01T10:00:00Z',
      verified_at: null,
      rejection_reason: null,
      supersedes_id: 99,
      created_at: '2026-02-01T10:00:00Z',
      updated_at: '2026-02-01T10:00:00Z',
    })

    renderReupload({
      checklistItemTemplateId: null,
      supersedesDocumentId: 99,
      onUploaded,
    })

    const input = screen.getByTestId('checklist-item-reupload-adhoc-input')
    const file = makeFile('sop-v2.pdf', 'application/pdf')
    await user.upload(input, file)

    await waitFor(() => {
      expect(onUploaded).toHaveBeenCalledTimes(1)
    })
    expect(screen.queryByTestId('checklist-item-reupload-adhoc-status')).not.toBeInTheDocument()
  })

  it('surfaces backend validation errors (e.g. superseding an approved row)', async () => {
    const user = userEvent.setup()
    uploadStudentDocumentMock.mockRejectedValueOnce(
      Object.assign(
        new Error(
          "supersedes_document_id must reference a rejected document (current status: 'approved')",
        ),
        { status: 422 },
      ),
    )

    renderReupload()

    const input = screen.getByTestId('checklist-item-reupload-11-input')
    await user.upload(input, makeFile('x.pdf', 'application/pdf'))

    expect(
      await screen.findByTestId('checklist-item-reupload-11-error'),
    ).toHaveTextContent("current status: 'approved'")
  })

  it('surfaces storage outage errors inline', async () => {
    const user = userEvent.setup()
    uploadStudentDocumentMock.mockRejectedValueOnce(
      Object.assign(new Error('Document storage is temporarily unavailable'), { status: 503 }),
    )

    renderReupload()

    const input = screen.getByTestId('checklist-item-reupload-11-input')
    await user.upload(input, makeFile('x.pdf', 'application/pdf'))

    expect(
      await screen.findByTestId('checklist-item-reupload-11-error'),
    ).toHaveTextContent('Document storage is temporarily unavailable')
  })

  it('rejects files larger than 10 MB client-side without hitting the API', async () => {
    const user = userEvent.setup()
    renderReupload()

    const input = screen.getByTestId('checklist-item-reupload-11-input')
    await user.upload(input, makeFile('huge.pdf', 'application/pdf', 11 * 1024 * 1024))

    expect(
      await screen.findByTestId('checklist-item-reupload-11-error'),
    ).toHaveTextContent('too large')
    expect(uploadStudentDocumentMock).not.toHaveBeenCalled()
  })

  it('rejects unsupported file extensions client-side', async () => {
    renderReupload()

    const input = screen.getByTestId('checklist-item-reupload-11-input')
    fireEvent.change(input, { target: { files: [makeFile('notes.txt', 'text/plain')] } })

    expect(
      await screen.findByTestId('checklist-item-reupload-11-error'),
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

    renderReupload()

    const input = screen.getByTestId('checklist-item-reupload-11-input')
    await user.upload(input, makeFile('a.pdf', 'application/pdf'))

    await waitFor(() => {
      expect(input).toBeDisabled()
    })

    resolveUpload({
      id: 1,
      status: 'pending',
      original_filename: 'a.pdf',
      supersedes_id: 42,
    })
  })

  it('disables the input when the disabled prop is set', () => {
    renderReupload({ disabled: true })
    expect(screen.getByTestId('checklist-item-reupload-11-input')).toBeDisabled()
  })

  it('uses the "adhoc" key for ad-hoc re-uploads (null template id)', () => {
    renderReupload({ checklistItemTemplateId: null, supersedesDocumentId: 99 })
    expect(screen.getByTestId('checklist-item-reupload-adhoc')).toBeInTheDocument()
    expect(screen.getByTestId('checklist-item-reupload-adhoc-input')).toBeInTheDocument()
    expect(screen.getByTestId('checklist-item-reupload-adhoc-trigger')).toBeInTheDocument()
  })

  it('clears the displayed error when a new file is picked', async () => {
    const user = userEvent.setup()
    uploadStudentDocumentMock
      .mockRejectedValueOnce(
        Object.assign(new Error('Storage outage'), { status: 503 }),
      )
      .mockResolvedValueOnce({
        id: 102,
        tenant_id: 10,
        application_id: 7,
        checklist_item_template_id: 11,
        status: 'pending',
        original_filename: 'b.pdf',
        content_type: 'application/pdf',
        size_bytes: 1024,
        storage_path: 'tenants/10/applications/7/abc.pdf',
        uploaded_by_user_id: 42,
        uploaded_at: '2026-02-01T10:00:00Z',
        verified_at: null,
        rejection_reason: null,
        supersedes_id: 42,
        created_at: '2026-02-01T10:00:00Z',
        updated_at: '2026-02-01T10:00:00Z',
      })

    renderReupload()

    const input = screen.getByTestId('checklist-item-reupload-11-input')
    await user.upload(input, makeFile('a.pdf', 'application/pdf'))
    expect(
      await screen.findByTestId('checklist-item-reupload-11-error'),
    ).toHaveTextContent('Storage outage')

    await user.upload(input, makeFile('b.pdf', 'application/pdf'))

    await waitFor(() => {
      expect(screen.queryByTestId('checklist-item-reupload-11-error')).not.toBeInTheDocument()
    })
  })
})