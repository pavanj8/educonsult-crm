import { useId, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../../api/client'
import { reassignCounselor } from '../../api/applications'

/**
 * Minimal shape of a staff member that can be selected as a counselor on the
 * reassignment control. Mirrors the ``Staff`` type's counselor-relevant
 * fields — the parent (future application detail view, E20; Journey J13)
 * filters the staff list to active counselors in the application's branch.
 */
export interface ReassignCounselorOption {
  id: number
  email: string
  is_active: boolean
}

export interface ReassignCounselorActionProps {
  applicationId: number
  /** Id of the counselor currently assigned, or ``null`` if unassigned. */
  currentCounselorId: number | null
  /**
   * Counselors eligible to be assigned. Parents are responsible for
   * scoping this to active counselors in the application's branch
   * (mirrors the backend's branch-scoped counselor validation on the
   * E20 endpoint, E20; Journey J13; issue #153). The control does not
   * filter beyond requiring the option to be active.
   */
  availableCounselors: ReassignCounselorOption[]
  /** Called after a successful reassignment so the host can refresh/close. */
  onReassigned?: (applicationId: number, counselorId: number | null) => void
  /**
   * When ``true`` the control renders as read-only (no edit / unassign
   * controls). Used when the current user lacks permission to reassign
   * counselors (e.g. counselor, document verifier, visa processor,
   * student). Defaults to ``false``.
   */
  readOnly?: boolean
}

function mapError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to reassign this application"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) {
      return err.message || 'The selected counselor could not be assigned to this application'
    }
  }
  return 'Failed to reassign the counselor'
}

function describeCurrentAssignment(
  currentCounselorId: number | null,
  counselors: ReassignCounselorOption[],
): string {
  if (currentCounselorId == null) {
    return 'Unassigned'
  }
  const match = counselors.find((option) => option.id === currentCounselorId)
  return match ? match.email : `Counselor #${currentCounselorId}`
}

/**
 * Staff "Reassign counselor" control for an application (E20; Journey J13;
 * frontend #154). Rendered on the application detail view, lets a
 * branch manager / receptionist / consultancy owner pick a new counselor
 * (or unassign the current one) from a pre-filtered list of branch-scoped
 * counselors. Backed by ``PATCH /applications/{id}/counselor``.
 *
 * The control is intentionally self-contained: the parent supplies the
 * eligible counselors so the parent (not this component) owns branch /
 * role scoping decisions. Server-side permission checks on the endpoint
 * remain authoritative; the UI maps 403 / 404 / 422 to readable errors
 * and keeps the form open so the operator can retry or cancel.
 */
export default function ReassignCounselorAction({
  applicationId,
  currentCounselorId,
  availableCounselors,
  onReassigned,
  readOnly = false,
}: ReassignCounselorActionProps) {
  const [open, setOpen] = useState(false)
  // The select's controlled value lives in component state — initialised
  // to the current assignment each time the form is opened so cancelling
  // does not leak an unsaved pick into the parent's view of the
  // application.
  const [selection, setSelection] = useState<string>(
    currentCounselorId == null ? '' : String(currentCounselorId),
  )
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const selectId = useId()
  const errorId = useId()

  const activeCounselors = useMemo(
    () => availableCounselors.filter((option) => option.is_active),
    [availableCounselors],
  )

  // Build the option list, always offering "Unassigned" as a first choice
  // so the operator can clear the current counselor. The "current" counselor
  // remains selectable in case it is active and the operator changes their
  // mind.
  const optionEntries = useMemo(
    () => [
      { id: '', label: 'Unassigned' },
      ...activeCounselors.map((option) => ({
        id: String(option.id),
        label: option.email,
      })),
    ],
    [activeCounselors],
  )

  function handleOpen() {
    setSubmitError(null)
    setSelection(currentCounselorId == null ? '' : String(currentCounselorId))
    setDone(false)
    setOpen(true)
  }

  function handleCancel() {
    setSubmitError(null)
    setOpen(false)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)

    // Empty string === "Unassigned" choice in the option list above.
    const parsed = selection === '' ? null : Number(selection)
    if (selection !== '' && (!Number.isInteger(parsed) || parsed! < 1)) {
      setSubmitError('Select a valid counselor or "Unassigned".')
      return
    }

    const nextCounselorId: number | null = parsed

    setSubmitting(true)
    try {
      await reassignCounselor(applicationId, nextCounselorId)
      setDone(true)
      onReassigned?.(applicationId, nextCounselorId)
    } catch (err) {
      setSubmitError(mapError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const currentLabel = describeCurrentAssignment(currentCounselorId, availableCounselors)

  if (done) {
    return (
      <p
        role="status"
        data-testid={`reassign-counselor-success-${applicationId}`}
        aria-live="polite"
      >
        Counselor reassignment saved.
      </p>
    )
  }

  if (readOnly || !open) {
    return (
      <div data-testid={`reassign-counselor-summary-${applicationId}`}>
        <p>
          Assigned counselor: <span data-testid={`reassign-counselor-current-${applicationId}`}>{currentLabel}</span>
        </p>
        {!readOnly ? (
          <button
            type="button"
            data-testid={`reassign-counselor-open-${applicationId}`}
            onClick={handleOpen}
          >
            Reassign counselor
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid={`reassign-counselor-form-${applicationId}`}
      aria-label="Reassign counselor"
    >
      <label htmlFor={selectId}>Assigned counselor</label>
      <select
        id={selectId}
        data-testid={`reassign-counselor-select-${applicationId}`}
        value={selection}
        onChange={(event) => setSelection(event.target.value)}
        disabled={submitting}
        aria-describedby={submitError ? errorId : undefined}
      >
        {optionEntries.map((option) => (
          <option key={option.id || 'unassigned'} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
      {submitError ? (
        <p
          id={errorId}
          role="alert"
          data-testid={`reassign-counselor-error-${applicationId}`}
        >
          {submitError}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={submitting}
        data-testid={`reassign-counselor-submit-${applicationId}`}
      >
        {submitting ? 'Reassigning…' : 'Save reassignment'}
      </button>
      <button
        type="button"
        onClick={handleCancel}
        disabled={submitting}
        data-testid={`reassign-counselor-cancel-${applicationId}`}
      >
        Cancel
      </button>
    </form>
  )
}
