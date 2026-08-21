import {
  DOCUMENT_UPLOAD_STATUS_LABELS,
  type ChecklistItem,
  type ChecklistUpload,
} from '../../types/checklist'

/**
 * Props for {@link ChecklistView}.
 *
 * The component is intentionally dumb: it takes the merged checklist
 * payload (already fetched and scoped to a single application) and
 * renders it. All loading / error / network state is owned by the
 * caller via {@link useApplicationChecklist} so this component stays
 * trivially testable and reusable.
 */
export interface ChecklistViewProps {
  applicationId: number
  items: ChecklistItem[]
  loading: boolean
  error: string | null
  onReload?: () => void
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  return date.toLocaleString()
}

function statusBadge(upload: ChecklistUpload | null): {
  label: string
  modifier: string
  testId: string
} {
  if (upload === null) {
    return {
      label: 'Not uploaded',
      modifier: 'checklist-item__status--not-uploaded',
      testId: 'not-uploaded',
    }
  }
  const status = upload.status
  return {
    label: DOCUMENT_UPLOAD_STATUS_LABELS[status],
    modifier: `checklist-item__status--${status}`,
    testId: status,
  }
}

/**
 * Render the merged E26 document checklist (Journey J19).
 *
 * One row per :class:`ChecklistItemTemplate` (E15) showing:
 *
 * * the template name, description, required flag, and stage,
 * * the latest upload status (Not uploaded / Pending review / Approved /
 *   Rejected),
 * * the uploaded filename + timestamp when an upload exists,
 * * the rejection reason when the latest upload was rejected.
 *
 * Loading / error / empty states follow the same conventions as the
 * rest of the student dashboard so the panel fits visually.
 */
export default function ChecklistView({
  applicationId,
  items,
  loading,
  error,
  onReload,
}: ChecklistViewProps) {
  return (
    <section
      className="checklist-view"
      aria-labelledby={`checklist-heading-${applicationId}`}
      data-testid={`checklist-view-${applicationId}`}
    >
      <header className="checklist-view__header">
        <h3 id={`checklist-heading-${applicationId}`} className="checklist-view__title">
          Document checklist
        </h3>
        {onReload ? (
          <button
            type="button"
            className="checklist-view__reload"
            data-testid={`checklist-reload-${applicationId}`}
            onClick={onReload}
            disabled={loading}
          >
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        ) : null}
      </header>

      {loading && <p className="checklist-view__status">Loading checklist…</p>}
      {error && (
        <p className="checklist-view__status checklist-view__status--error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="checklist-view__status">No documents required at this stage.</p>
      )}
      {!loading && !error && items.length > 0 && (
        <ul className="checklist-view__list">
          {items.map((item) => {
            const badge = statusBadge(item.upload)
            return (
              <li
                key={item.templateId}
                className="checklist-item"
                data-testid={`checklist-item-${item.templateId}`}
              >
                <div className="checklist-item__header">
                  <h4 className="checklist-item__name">
                    {item.name}
                    {item.required ? (
                      <span
                        className="checklist-item__required"
                        aria-label="required"
                        data-testid={`checklist-item-required-${item.templateId}`}
                      >
                        {' '}
                        (required)
                      </span>
                    ) : null}
                  </h4>
                  <span
                    className={`checklist-item__status ${badge.modifier}`}
                    data-testid={`checklist-item-status-${item.templateId}`}
                    data-status={badge.testId}
                  >
                    {badge.label}
                  </span>
                </div>
                {item.description ? (
                  <p className="checklist-item__description">{item.description}</p>
                ) : null}
                {item.upload ? (
                  <div className="checklist-item__upload">
                    <p className="checklist-item__filename">
                      <span className="checklist-item__filename-label">Uploaded:</span>{' '}
                      {item.upload.originalFilename}
                    </p>
                    <p className="checklist-item__uploaded-at">
                      <time dateTime={item.upload.uploadedAt}>
                        {formatTimestamp(item.upload.uploadedAt)}
                      </time>
                    </p>
                    {item.upload.status === 'rejected' && item.upload.rejectionReason ? (
                      <p
                        className="checklist-item__rejection"
                        data-testid={`checklist-item-rejection-${item.templateId}`}
                      >
                        <span className="checklist-item__rejection-label">
                          Verifier comment:
                        </span>{' '}
                        {item.upload.rejectionReason}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}