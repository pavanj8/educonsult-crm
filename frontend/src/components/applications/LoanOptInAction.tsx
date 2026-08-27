import { useState } from 'react'

import { isApiError } from '../../api/client'
import { setLoanOptIn } from '../../api/applications'

export interface LoanOptInActionProps {
  applicationId: number
  loanOptIn: boolean
  /**
   * Called after a successful opt-in / opt-out so the host can refresh
   * the application state (mirrors the ReassignCounselorAction contract,
   * E20; frontend #154).
   */
  onChanged?: (applicationId: number, loanOptIn: boolean) => void
}

function mapError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to update this application"
    if (err.status === 404) {
      return 'This application is no longer available'
    }
    if (err.status === 422) {
      return err.message || 'The loan-tracking preference could not be saved'
    }
  }
  return 'Failed to update the loan-tracking preference'
}

/**
 * Student-facing loan opt-in toggle (E36; Journey J29; frontend #199).
 *
 * Rendered on the student application row, this control surfaces the
 * application's current ``loan_opt_in`` flag (Requirements §5:
 * "Loans: Tracking-only fields (opted-in, status, amount, lender) —
 * no separate loan officer workflow for v1") and lets the student
 * toggle it on or off. The backend persistence is the
 * ``PATCH /applications/{id}/loan-opt-in`` endpoint, which is a
 * student-only endpoint that returns the full updated ``Application``
 * payload. The staff-side ``status / lender / amount`` fields are
 * tracked separately under E37 (Journey J30) and are intentionally
 * out of scope for this control.
 *
 * The control stays disabled while the request is in flight so the
 * student cannot fire two concurrent toggles for the same
 * application.
 *
 * After a successful toggle, the control reflects the new state
 * immediately (button label flips to the inverse action, status
 * text updates) so the student sees the change take effect. The
 * ``onChanged`` callback is then invoked so the parent can reload
 * or update its application list if it needs the refreshed
 * ``updated_at`` timestamp or other server-side changes.
 */
export default function LoanOptInAction({
  applicationId,
  loanOptIn: initialLoanOptIn,
  onChanged,
}: LoanOptInActionProps) {
  const [localLoanOptIn, setLocalLoanOptIn] = useState(initialLoanOptIn)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Re-sync when the PROP changes (e.g. after a parent reload). Comparing the
  // previous prop rather than the local value matters: right after an
  // optimistic toggle, local and prop legitimately disagree, and comparing
  // against the prop directly would immediately revert the optimistic update
  // on the very next render.
  const [prevLoanOptIn, setPrevLoanOptIn] = useState(initialLoanOptIn)
  if (prevLoanOptIn !== initialLoanOptIn) {
    setPrevLoanOptIn(initialLoanOptIn)
    setLocalLoanOptIn(initialLoanOptIn)
  }

  async function handleToggle() {
    const newValue = !localLoanOptIn
    setSubmitError(null)
    setSubmitting(true)
    try {
      await setLoanOptIn(applicationId, newValue)
      // Optimistically update local state so the UI reflects the change immediately
      setLocalLoanOptIn(newValue)
      onChanged?.(applicationId, newValue)
    } catch (err) {
      setSubmitError(mapError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const label = localLoanOptIn ? 'Opt out of loan tracking' : 'Opt in to loan tracking'
  const statusLabel = localLoanOptIn ? 'Opted in' : 'Not opted in'

  return (
    <div className="loan-opt-in-action" data-testid={`loan-opt-in-action-${applicationId}`}>
      <p className="loan-opt-in-action__status">
        Loan tracking:{' '}
        <span
          className="loan-opt-in-action__status-value"
          data-testid={`loan-opt-in-status-${applicationId}`}
          data-loan-opt-in={localLoanOptIn ? 'true' : 'false'}
        >
          {statusLabel}
        </span>
      </p>
      <button
        type="button"
        onClick={handleToggle}
        disabled={submitting}
        aria-busy={submitting}
        data-testid={`loan-opt-in-toggle-${applicationId}`}
      >
        {submitting ? 'Saving…' : label}
      </button>
      {submitError ? (
        <p
          role="alert"
          className="loan-opt-in-action__error"
          data-testid={`loan-opt-in-error-${applicationId}`}
        >
          {submitError}
        </p>
      ) : null}
    </div>
  )
}