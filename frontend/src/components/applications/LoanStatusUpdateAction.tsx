import { useEffect, useId, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../../api/client'
import { updateApplicationLoan, type UpdateLoanRequest } from '../../api/applications'
import {
  formatCurrencyAmount,
  isSupportedCurrencyCodeValue,
  normalizeCurrencyCode,
  useDisplayCurrency,
} from '../currency'
import type { Application } from '../../types/application'

export interface LoanStatusUpdateActionProps {
  applicationId: number
  /**
   * Snapshot of the application's currently-recorded loan fields.
   * The component pre-fills its form from these values when it first
   * mounts (and whenever they change). When the application has no
   * loan data yet, supply ``null`` for every field and the form
   * starts blank. The host is responsible for keeping this in sync
   * with its queue data source (e.g. the
   * :ts:func:`useAssignedApplications` hook).
   */
  initialLoan: {
    loan_status: string | null
    loan_lender: string | null
    /**
     * Loan amount as a JSON-decoded string (the backend's
     * ``Numeric(12, 2)`` column round-trips through Pydantic v2 as a
     * JSON string for precision). ``null`` when not recorded yet.
     */
    loan_amount: string | null
  }
  /** Called after a successful save with the freshly-persisted application. */
  onSaved?: (applicationId: number, application: Application) => void
  /**
   * When ``true`` the control renders as read-only: no inputs are
   * enabled, no Save button is shown. Used when the signed-in user
   * lacks ``loan:update`` permission (e.g. counselor, document
   * verifier, visa processor, receptionist, student, super admin).
   * Defaults to ``false``.
   */
  readOnly?: boolean
}

interface LoanFormState {
  loan_status: string
  loan_lender: string
  /**
   * The amount as entered by the operator in a ``<input
   * type="number">``. Stored as a string (including the empty
   * string for "no entry") so the operator can type
   * ``"1500000.50"`` without IEEE-754 rounding; the API client
   * forwards the string verbatim to the backend's ``Decimal``
   * Pydantic field, which accepts JSON strings for ``Numeric``
   * columns and round-trips through :class:`Decimal` without loss.
   */
  loan_amount: string
}

const EMPTY_LOAN = {
  loan_status: null,
  loan_lender: null,
  loan_amount: null,
} as const

const MAX_LOAN_STATUS = 32
const MAX_LOAN_LENDER = 120

const NUMERIC_FIELD_FRACTION_DIGITS = 2

function mapError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return 'Your session has expired — please sign in again'
    if (err.status === 403) return "You don't have permission to update this application's loan tracking fields"
    if (err.status === 404) return 'This application is no longer available'
    if (err.status === 422) {
      return (
        err.message ||
        'The loan tracking fields could not be saved (check the status, lender, and amount)'
      )
    }
  }
  return 'Failed to save the loan tracking fields'
}

function emptyForm(): LoanFormState {
  return { loan_status: '', loan_lender: '', loan_amount: '' }
}

function formFromLoan(loan: LoanStatusUpdateActionProps['initialLoan']): LoanFormState {
  return {
    loan_status: loan.loan_status ?? '',
    loan_lender: loan.loan_lender ?? '',
    loan_amount: loan.loan_amount ?? '',
  }
}

/**
 * Parse the amount string the operator typed in the ``<input
 * type="number">`` into a JSON-string ``Decimal`` value for the
 * backend's ``Numeric(12, 2)`` column. Returns:
 *
 * * ``null`` for an empty string (caller intends "clear the field"
 *   OR "did not enter an amount") — the backend treats ``null`` as
 *   an explicit clear when the field is present in the PATCH body.
 * * The trimmed string otherwise (e.g. ``"1500000"`` → ``"1500000"``,
 *   ``"1500000.5"`` → ``"1500000.5"``).
 *
 * The string is left untouched (not coerced to a number) so the
 * backend's Pydantic ``Decimal`` parser can round-trip the value
 * without float precision loss. Negative numbers are rejected here
 * rather than relying on the browser's native ``min`` attribute so
 * the error message is consistent across the form's other
 * validation paths.
 */
function parseLoanAmountInput(raw: string): { value: string | null; error: string | null } {
  const trimmed = raw.trim()
  if (trimmed === '') {
    return { value: null, error: null }
  }
  if (!/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return { value: null, error: 'Please enter a non-negative number for the loan amount.' }
  }
  const numeric = Number(trimmed)
  if (!Number.isFinite(numeric)) {
    return { value: null, error: 'Please enter a valid number for the loan amount.' }
  }
  if (numeric < 0) {
    return { value: null, error: 'Loan amount cannot be negative.' }
  }
  return { value: trimmed, error: null }
}

/**
 * Render a JSON-string Decimal (the wire format used by the backend's
 * Pydantic ``Numeric(12, 2)`` columns) as a human-readable amount
 * string in the active tenant's display currency. Returns the raw
 * value when the input cannot be parsed (so a stale "not-yet-loaded"
 * state never blanks the row).
 */
function formatLoanAmount(value: string | null): string {
  if (value === null || value === '') return '—'
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return value
  // Render with up to NUMERIC_FIELD_FRACTION_DIGITS decimals (matching the
  // Numeric(12, 2) precision the backend stores). Drop the trailing zeros
  // so a bare "1500000" does not render as "1,500,000.00".
  return parsed.toLocaleString(undefined, {
    maximumFractionDigits: NUMERIC_FIELD_FRACTION_DIGITS,
  })
}

/**
 * Render the loan amount using the resolved display currency code. Falls
 * back to the locale-formatted raw value (without a currency code)
 * when the resolved code is not in the curated support list or cannot
 * be parsed, so a stale tenant record never blanks the row.
 */
function renderReadOnlyLoanAmount(
  amount: string | null,
  currencyCode: string,
): string {
  if (amount === null) return '—'
  let normalized: string
  try {
    normalized = normalizeCurrencyCode(currencyCode)
  } catch {
    return formatLoanAmount(amount)
  }
  if (!isSupportedCurrencyCodeValue(normalized)) {
    return formatLoanAmount(amount)
  }
  try {
    return formatCurrencyAmount(amount, normalized).display
  } catch {
    return formatLoanAmount(amount)
  }
}

/**
 * Staff "Loan status update" control for an application (E37; Journey J30;
 * frontend #201). Lets a Consultancy Owner or Branch Manager record the
 * loan status, lender, and amount against an application once the
 * student has opted in (E36; Journey J29). Backed by
 * ``PATCH /applications/{id}/loan``.
 *
 * The component is intentionally self-contained — the host page supplies
 * the application's currently-recorded loan fields via ``initialLoan``
 * (so the form can be pre-filled on mount without a separate GET) and
 * an ``onSaved`` callback (so the host can refresh its queue data
 * source). It mirrors the conventions used by
 * :ts:comp:`VisaDetailUpdateForm` (E34) and
 * :ts:comp:`ReassignCounselorAction` (E20) so the staff surfaces across
 * the platform read consistently.
 *
 * Validation:
 *
 * * ``loan_status`` is trimmed of surrounding whitespace; empty /
 *   whitespace-only collapses to ``null`` (an explicit clear, matching
 *   the backend's contract on :class:`UpdateLoanRequest`). The
 *   32-char ceiling matches the persisted column on
 *   :class:`app.models.application.Application`.
 * * ``loan_lender`` is trimmed the same way; the 120-char ceiling
 *   matches the persisted column.
 * * ``loan_amount`` is parsed as a non-negative decimal. Zero is
 *   allowed (a fully scholarshipped loan is a real edge case); the
 *   value is forwarded as a JSON-decoded string so the backend's
 *   ``Numeric(12, 2)`` column round-trips without precision loss.
 *
 * The component is read-only when ``readOnly`` is ``true`` (the
 * signed-in user lacks ``loan:update`` — e.g. counselor, document
 * verifier, visa processor, receptionist, student, super admin).
 * Read-only mode renders a compact summary; the displayed amount is
 * rendered currency-aware (E52; Requirements §1 Currency) via the
 * shared :func:`formatCurrencyAmount` helper using the active tenant's
 * display currency.
 */
export default function LoanStatusUpdateAction({
  applicationId,
  initialLoan,
  onSaved,
  readOnly = false,
}: LoanStatusUpdateActionProps) {
  const [form, setForm] = useState<LoanFormState>(() => formFromLoan(initialLoan))
  const [submitting, setSubmitting] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const statusId = useId()
  const lenderId = useId()
  const amountId = useId()
  const validationErrorId = useId()
  const submitErrorId = useId()

  // Resolve the active tenant's display currency once per render. The
  // hook is unconditional (rules of hooks) but the cost is trivial:
  // it just reads the auth state and the cached tenant branding
  // record. When no auth context is available (e.g. unit tests) the
  // hook still returns a usable default currency code so the
  // read-only rendering never throws.
  const displayCurrency = useDisplayCurrency()

  // Re-sync the form when the host's loan snapshot changes (e.g. the
  // parent refreshed its queue and a sibling ticket landed new data).
  // This keeps the form in step with the host without forcing the
  // parent to imperatively reset our local state.
  useEffect(() => {
    setForm(formFromLoan(initialLoan))
    setDone(false)
    setSubmitError(null)
    setValidationError(null)
  }, [initialLoan])

  const statusRemaining = MAX_LOAN_STATUS - form.loan_status.length
  const lenderRemaining = MAX_LOAN_LENDER - form.loan_lender.length

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)
    setValidationError(null)

    const trimmedStatus = form.loan_status.trim()
    const trimmedLender = form.loan_lender.trim()

    if (trimmedStatus.length > MAX_LOAN_STATUS) {
      setValidationError(`Loan status must be ${MAX_LOAN_STATUS} characters or fewer.`)
      return
    }
    if (trimmedLender.length > MAX_LOAN_LENDER) {
      setValidationError(`Loan lender must be ${MAX_LOAN_LENDER} characters or fewer.`)
      return
    }

    const { value: amountValue, error: amountError } = parseLoanAmountInput(form.loan_amount)
    if (amountError !== null) {
      setValidationError(amountError)
      return
    }

  // Build the PATCH body. The contract is: which keys are present
  // in the JSON body determines which columns the backend updates
  // (via :attr:`pydantic.BaseModel.model_fields_set`). An absent
  // field is a no-op; a present field with ``null`` clears the
  // persisted value; a present field with a string updates it.
  //
  // We compare the operator's *current* entry against the initial
  // snapshot to decide whether the field changed:
  //
  // * If the field is byte-identical to the initial raw value
  //   (operator left it alone), omit it. This is how the form
  //   achieves the partial-update contract: a PATCH that only
  //   changes ``loan_status`` does not resend ``loan_lender`` /
  //   ``loan_amount`` (the backend treats them as no-ops and
  //   preserves the persisted values).
  // * Otherwise the operator typed something different (a real
  //   value, a corrected whitespace, or a single-space-to-empty
  //   clear), so we send the trimmed value (``null`` when the
  //   trimmed result is empty so the backend clears the
  //   persisted column).
  //
  // Comparing the *raw* form value (not the trimmed one) is
  // important: an operator who types a single space into a
  // previously-empty field has actively expressed an intent to
  // interact with it, and the backend's own whitespace validator
  // strips whitespace-only strings to ``null`` — so the
  // round-tripped clear lands on the persisted column. Comparing
  // trimmed values (as the previous iteration did) silently
  // dropped that intent.
  const body: UpdateLoanRequest = {}
  if (form.loan_status !== (initialLoan.loan_status ?? '')) {
    body.loan_status = trimmedStatus === '' ? null : trimmedStatus
  }
  if (form.loan_lender !== (initialLoan.loan_lender ?? '')) {
    body.loan_lender = trimmedLender === '' ? null : trimmedLender
  }
  if (form.loan_amount !== (initialLoan.loan_amount ?? '')) {
    body.loan_amount = amountValue
  }

    setSubmitting(true)
    try {
      const saved = await updateApplicationLoan(applicationId, body)
      setDone(true)
      onSaved?.(applicationId, saved)
    } catch (err) {
      setSubmitError(mapError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const describedBy =
    [validationError ? validationErrorId : null, submitError ? submitErrorId : null]
      .filter(Boolean)
      .join(' ') || undefined

  if (done) {
    return (
      <p
        role="status"
        aria-live="polite"
        data-testid={`loan-status-success-${applicationId}`}
      >
        Loan tracking fields saved.
      </p>
    )
  }

  if (readOnly) {
    const formattedAmount = renderReadOnlyLoanAmount(
      initialLoan.loan_amount,
      displayCurrency.code,
    )
    return (
      <div data-testid={`loan-status-readonly-${applicationId}`}>
        <p>
          Loan status:{' '}
          <span data-testid={`loan-status-readonly-status-${applicationId}`}>
            {initialLoan.loan_status ?? '—'}
          </span>
        </p>
        <p>
          Loan lender:{' '}
          <span data-testid={`loan-status-readonly-lender-${applicationId}`}>
            {initialLoan.loan_lender ?? '—'}
          </span>
        </p>
        <p>
          Loan amount:{' '}
          <span
            data-testid={`loan-status-readonly-amount-${applicationId}`}
            data-currency-code={displayCurrency.code}
          >
            {formattedAmount}
          </span>
        </p>
      </div>
    )
  }

  const hasNothingRecorded =
    initialLoan.loan_status === EMPTY_LOAN.loan_status &&
    initialLoan.loan_lender === EMPTY_LOAN.loan_lender &&
    initialLoan.loan_amount === EMPTY_LOAN.loan_amount

  return (
    <form
      onSubmit={handleSubmit}
      data-testid={`loan-status-form-${applicationId}`}
      aria-label="Update loan tracking fields"
    >
      <p data-testid={`loan-status-form-hint-${applicationId}`}>
        {hasNothingRecorded
          ? 'No loan tracking fields have been recorded yet for this application.'
          : 'Update the loan tracking fields recorded for this application.'}
      </p>
      <div>
        <label htmlFor={statusId}>
          Loan status <span aria-hidden="true">(optional)</span>
        </label>
        <input
          id={statusId}
          type="text"
          value={form.loan_status}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, loan_status: event.target.value }))
          }
          maxLength={MAX_LOAN_STATUS}
          aria-describedby={describedBy}
          disabled={submitting}
          data-testid={`loan-status-status-${applicationId}`}
        />
        <p data-testid={`loan-status-status-counter-${applicationId}`}>
          {statusRemaining} characters remaining
        </p>
      </div>
      <div>
        <label htmlFor={lenderId}>
          Loan lender <span aria-hidden="true">(optional)</span>
        </label>
        <input
          id={lenderId}
          type="text"
          value={form.loan_lender}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, loan_lender: event.target.value }))
          }
          maxLength={MAX_LOAN_LENDER}
          aria-describedby={describedBy}
          disabled={submitting}
          data-testid={`loan-status-lender-${applicationId}`}
        />
        <p data-testid={`loan-status-lender-counter-${applicationId}`}>
          {lenderRemaining} characters remaining
        </p>
      </div>
      <div>
        <label htmlFor={amountId}>
          Loan amount <span aria-hidden="true">(optional)</span>
        </label>
        <input
          id={amountId}
          type="number"
          inputMode="decimal"
          min={0}
          step="0.01"
          value={form.loan_amount}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, loan_amount: event.target.value }))
          }
          aria-describedby={describedBy}
          disabled={submitting}
          data-testid={`loan-status-amount-${applicationId}`}
        />
      </div>
      {validationError ? (
        <p
          id={validationErrorId}
          role="alert"
          data-testid={`loan-status-validation-${applicationId}`}
        >
          {validationError}
        </p>
      ) : null}
      {submitError ? (
        <p
          id={submitErrorId}
          role="alert"
          data-testid={`loan-status-error-${applicationId}`}
        >
          {submitError}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={submitting}
        data-testid={`loan-status-submit-${applicationId}`}
      >
        {submitting ? 'Saving…' : 'Save loan tracking fields'}
      </button>
      <button
        type="button"
        onClick={() => {
          setForm(emptyForm())
          setValidationError(null)
          setSubmitError(null)
        }}
        disabled={submitting}
        data-testid={`loan-status-clear-${applicationId}`}
      >
        Clear form
      </button>
    </form>
  )
}

// Re-export the read-only formatter and the amount-input parser so
// unit tests can pin their contracts without having to re-derive them
// from the component's private helpers.
export const __testing = { renderReadOnlyLoanAmount, parseLoanAmountInput }
