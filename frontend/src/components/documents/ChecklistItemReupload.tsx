import { useId, useState } from 'react'
import type { ChangeEvent } from 'react'

import { useStudentDocumentUpload } from '../../hooks/useStudentDocumentUpload'

/**
 * Maximum upload size in bytes (Requirements §5: default 10 MB).
 *
 * Mirrors :data:`ChecklistItemUpload`'s cap. Kept as a local constant
 * (instead of imported) so the re-upload control is self-contained
 * and any future divergence (e.g. a per-tenant policy) can be applied
 * here without touching the initial-upload component.
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

/**
 * Props for {@link ChecklistItemReupload}.
 *
 * Renders the re-upload affordance for one checklist item whose most
 * recent upload was rejected by a Document Verifier (J23). The student
 * picks a replacement file; the upload hook forwards the rejected
 * row's id as ``supersedes_document_id`` (E31 / Journey J24 /
 * sibling backend ticket #187) so the new row carries an audit-trail
 * link back to the rejected predecessor.
 *
 * The parent ({@link ChecklistView}) supplies the application id,
 * template id, and the rejected ``supersedesDocumentId`` (the
 * :class:`StudentDocument` row id of the rejected upload). After a
 * successful re-upload the parent is asked to reload the merged
 * checklist so the new row shows up in the right state (pending →
 * verifier reviews → approved/rejected).
 */
export interface ChecklistItemReuploadProps {
  applicationId: number
  checklistItemTemplateId: number | null
  /**
   * Id of the previously-rejected :class:`StudentDocument` this
   * upload replaces. Required: the backend rejects any
   * ``supersedes_document_id`` that is not in ``rejected`` status or
   * does not belong to this application, so the parent must only
   * render this control when the latest upload is rejected.
   */
  supersedesDocumentId: number
  /**
   * Called after a successful re-upload so the parent can refresh
   * the merged checklist payload. The hook does not own checklist
   * state.
   */
  onUploaded?: () => void
  /**
   * When ``true`` the form is rendered disabled (e.g. while the
   * parent is loading the merged checklist). Defaults to ``false``.
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
 * Re-upload control for a rejected checklist item (E31; Journey J24).
 *
 * Visually and structurally mirrors {@link ChecklistItemUpload} so
 * the two flows feel identical to the student, but wires the upload
 * through the backend's ``supersedes_document_id`` form field (E31;
 * sibling backend ticket #187). On success the parent reloads the
 * merged checklist so the new row appears in ``pending`` status and
 * the rejected row stays visible in the audit trail. On failure, the
 * backend's ``detail`` message is surfaced inline (no silent
 * swallowing).
 *
 * The component is rendered alongside the rejection block by
 * {@link ChecklistView} and only fires when the latest upload is in
 * ``rejected`` status — see :data:`ChecklistViewProps.items` and the
 * ``upload.status`` branch in :func:`ChecklistView`.
 */
export default function ChecklistItemReupload({
  applicationId,
  checklistItemTemplateId,
  supersedesDocumentId,
  onUploaded,
  disabled = false,
}: ChecklistItemReuploadProps) {
  const inputId = useId()
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [clientError, setClientError] = useState<string | null>(null)
  const { uploading, error, upload, clearError } = useStudentDocumentUpload({
    applicationId,
    checklistItemTemplateId,
    supersedesDocumentId,
  })

  const displayedError = clientError ?? error
  // The test-id suffix is namespaced off the template id (or ``adhoc``
  // for ad-hoc uploads) so the re-upload control is independently
  // addressable in tests and never collides with the initial-upload
  // control's test ids.
  const suffix = checklistItemTemplateId === null ? 'adhoc' : String(checklistItemTemplateId)
  const testIdPrefix = `checklist-item-reupload-${suffix}`

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
    <div className="checklist-item__reupload-control" data-testid={testIdPrefix}>
      <p className="checklist-item__reupload-help">
        Upload a corrected version to replace the rejected file.
      </p>
      <label
        className="checklist-item__upload-trigger"
        htmlFor={inputId}
        data-testid={`${testIdPrefix}-trigger`}
      >
        Re-upload file
      </label>
      <input
        id={inputId}
        data-testid={`${testIdPrefix}-input`}
        className="visually-hidden"
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.docx,application/pdf,image/jpeg,image/png,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={handleFileChange}
        disabled={disabled || uploading}
      />
      {selectedName ? (
        <p
          className="checklist-item__upload-filename"
          data-testid={`${testIdPrefix}-filename`}
        >
          {selectedName}
        </p>
      ) : null}
      {uploading ? (
        <p
          className="checklist-item__upload-status"
          data-testid={`${testIdPrefix}-status`}
          role="status"
        >
          Uploading…
        </p>
      ) : null}
      {displayedError ? (
        <p
          className="checklist-item__upload-error"
          data-testid={`${testIdPrefix}-error`}
          role="alert"
        >
          {displayedError}
        </p>
      ) : null}
    </div>
  )
}