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
 * "Loans: Tracking-only fields (opted-in, status, amount, lender) — no
 * separate loan officer workflow for v1") and lets the student toggle
 * it on or off. The backend persistence is the
 * ``PATCH /applications/{id}/loan-opt-in`` endpoint which is the
 * follow-up to this issue (the E36 backend field was added in #198;
 * the toggle endpoint is a natural follow-up because the loan
 * status / lender / amount fields are tracked separately in E37).
 *
 * Until the backend endpoint exists, calls to ``setLoanOptIn`` will
 * return 404 from the API client; the UI surfaces that as a readable
 * "This application is no longer available" / "Failed to update"
 * error so the student sees the toggle attempt is acknowledged, not
 * silently dropped. The control stays disabled while the request is
 * in flight so the student cannot fire two concurrent toggles for
 * the same application.
 */
export default function LoanOptInAction({
  applicationId,
  loanOptIn,
  onChanged,
}: LoanOptInActionProps) {
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  async function handleToggle() {
    setSubmitError(null)
    setSubmitting(true)
    try {
      await setLoanOptIn(applicationId, !loanOptIn)
      onChanged?.(applicationId, !loanOptIn)
    } catch (err) {
      setSubmitError(mapError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const label = loanOptIn ? 'Opt out of loan tracking' : 'Opt in to loan tracking'
  const statusLabel = loanOptIn ? 'Opted in' : 'Not opted in'

  return (
    <div className="loan-opt-in-action" data-testid={`loan-opt-in-action-${applicationId}`}>
      <p className="loan-opt-in-action__status">
        Loan tracking:{' '}
        <span
          className="loan-opt-in-action__status-value"
          data-testid={`loan-opt-in-status-${applicationId}`}
          data-loan-opt-in={loanOptIn ? 'true' : 'false'}
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
