import { useId, useState } from 'react'
import type { ChangeEvent } from 'react'

import { useStudentDocumentUpload } from '../../hooks/useStudentDocumentUpload'

/**
 * Maximum upload size in bytes (Requirements §5: default 10 MB).
 *
 * TODO: this is a client-side guard only; the backend E27 #176 ticket
 * enforces the size limit authoritatively. If the backend policy ever
 * changes (e.g. to 5 MB), this constant must be updated in lockstep —
 * or, preferentially, fetched from a tenant-config endpoint so the two
 * layers cannot drift.
 */
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024

/** File extensions allowed by the backend (Requirements §5: PDF/JPG/PNG/DOCX). */
const ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'docx'] as const

const ALLOWED_MIME_TYPES: Record<string, true> = {
  'application/pdf': true,
  'image/jpeg': true,
  'image/png': true,
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': true,
}

/** Suffix used in ``data-testid`` keys for ad-hoc uploads (no template id). */
const ADHOC_KEY = 'adhoc' as const

function testIdSuffix(checklistItemTemplateId: number | null): string {
  return checklistItemTemplateId === null ? ADHOC_KEY : String(checklistItemTemplateId)
}

/**
 * Props for {@link ChecklistItemUpload}.
 *
 * Renders a single upload control for one checklist item. The parent
 * ({@link ChecklistView}) supplies the application id and template id;
 * after a successful upload the parent is asked to reload the merged
 * checklist so the just-uploaded row shows up in the right state
 * (pending → verifier reviews → approved/rejected).
 */
export interface ChecklistItemUploadProps {
  applicationId: number
  checklistItemTemplateId: number | null
  /**
   * Called after a successful upload so the parent can refresh the
   * merged checklist payload. The hook does not own checklist state.
   */
  onUploaded?: () => void
  /**
   * When ``true`` the form is rendered disabled (e.g. while the parent
   * is loading the merged checklist). Defaults to ``false``.
   */
  disabled?: boolean
}

function getExtension(filename: string): string | null {
  const dot = filename.lastIndexOf('.')
  if (dot < 0 || dot === filename.length - 1) {
    return null
  }
  return filename.slice(dot + 1).toLowerCase()
}

function isAllowedFile(file: File): { ok: true } | { ok: false; reason: string } {
  if (file.size > MAX_UPLOAD_BYTES) {
    return {
      ok: false,
      reason: `File is too large (max ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB)`,
    }
  }
  const ext = getExtension(file.name)
  const extOk = ext !== null && (ALLOWED_EXTENSIONS as readonly string[]).includes(ext)
  const mimeOk = file.type !== '' && ALLOWED_MIME_TYPES[file.type] === true
  // Pass when either the extension or the MIME type matches (clients
  // sometimes send the wrong MIME for PDF/DOCX; we accept either signal).
  if (!extOk && !mimeOk) {
    return {
      ok: false,
      reason: 'Only PDF, JPG, PNG, or DOCX files are allowed',
    }
  }
  return { ok: true }
}

/**
 * One checklist item's upload control (E27; Journey J20).
 *
 * Renders a hidden ``<input type="file">`` paired with a visible button
 * so the file picker stays accessible. Validates client-side before
 * reaching the backend (the backend re-validates via the #176 sibling
 * ticket). On success, calls ``onUploaded`` so the parent reloads the
 * merged checklist view; on failure, surfaces the backend's ``detail``
 * message inline (no silent swallowing).
 */
export default function ChecklistItemUpload({
  applicationId,
  checklistItemTemplateId,
  onUploaded,
  disabled = false,
}: ChecklistItemUploadProps) {
  const inputId = useId()
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [clientError, setClientError] = useState<string | null>(null)
  const { uploading, error, upload, clearError } = useStudentDocumentUpload({
    applicationId,
    checklistItemTemplateId,
  })

  const displayedError = clientError ?? error
  const suffix = testIdSuffix(checklistItemTemplateId)

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    // Always reset the input so picking the same file twice in a row
    // still fires ``onChange``.
    event.target.value = ''
    if (!file) {
      return
    }
    clearError()
    setClientError(null)
    setSelectedName(file.name)

    const allowed = isAllowedFile(file)
    if (!allowed.ok) {
      setClientError(allowed.reason)
      return
    }

    try {
      await upload(file)
      setSelectedName(null)
      onUploaded?.()
    } catch {
      // Error is already surfaced via the hook's ``error`` state.
    }
  }

  return (
    <div
      className="checklist-item__upload-control"
      data-testid={`checklist-item-upload-${suffix}`}
    >
      <label
        className="checklist-item__upload-trigger"
        htmlFor={inputId}
        data-testid={`checklist-item-upload-trigger-${suffix}`}
      >
        Upload file
      </label>
      <input
        id={inputId}
        data-testid={`checklist-item-upload-input-${suffix}`}
        className="visually-hidden"
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.docx,application/pdf,image/jpeg,image/png,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={handleFileChange}
        disabled={disabled || uploading}
      />
      {selectedName ? (
        <p
          className="checklist-item__upload-filename"
          data-testid={`checklist-item-upload-filename-${suffix}`}
        >
          {selectedName}
        </p>
      ) : null}
      {uploading ? (
        <p
          className="checklist-item__upload-status"
          data-testid={`checklist-item-upload-status-${suffix}`}
          role="status"
        >
          Uploading…
        </p>
      ) : null}
      {displayedError ? (
        <p
          className="checklist-item__upload-error"
          data-testid={`checklist-item-upload-error-${suffix}`}
          role="alert"
        >
          {displayedError}
        </p>
      ) : null}
    </div>
  )
}
