import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import LoanStatusUpdateAction, { __testing } from './LoanStatusUpdateAction'
import { updateApplicationLoan } from '../../api/applications'
import { AuthProvider } from '../../store/authStore'

vi.mock('../../api/applications', () => ({
  updateApplicationLoan: vi.fn(),
}))
const updateApplicationLoanMock = vi.mocked(updateApplicationLoan)

function apiError(status: number, message: string): Error {
  return Object.assign(new Error(message), { name: 'ApiError', status })
}

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

const EMPTY_LOAN = {
  loan_status: null,
  loan_lender: null,
  loan_amount: null,
}

const SAVED_APPLICATION = {
  id: 5,
  tenant_id: 10,
  student_id: 42,
  university_id: 1,
  program_id: 10,
  stage: 'loan_processing' as const,
  loan_status: 'approved',
  loan_lender: 'HDFC Credila',
  loan_amount: '1500000.00',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

describe('LoanStatusUpdateAction', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default to no fetch; tests that need it can install their own.
    globalThis.fetch = vi.fn() as typeof fetch
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders an empty form when no loan fields have been recorded yet', () => {
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} />,
      { wrapper },
    )

    expect(screen.getByTestId('loan-status-form-5')).toBeInTheDocument()
    expect((screen.getByTestId('loan-status-status-5') as HTMLInputElement).value).toBe('')
    expect((screen.getByTestId('loan-status-lender-5') as HTMLInputElement).value).toBe('')
    expect((screen.getByTestId('loan-status-amount-5') as HTMLInputElement).value).toBe('')
    expect(screen.getByTestId('loan-status-form-hint-5')).toHaveTextContent(
      /no loan tracking fields/i,
    )
  })

  it('pre-fills the form from the initialLoan snapshot', () => {
    render(
      <LoanStatusUpdateAction
        applicationId={5}
        initialLoan={{
          loan_status: 'in_progress',
          loan_lender: 'HDFC Credila',
          loan_amount: '1500000.00',
        }}
      />,
      { wrapper },
    )

    expect((screen.getByTestId('loan-status-status-5') as HTMLInputElement).value).toBe(
      'in_progress',
    )
    expect((screen.getByTestId('loan-status-lender-5') as HTMLInputElement).value).toBe(
      'HDFC Credila',
    )
    expect((screen.getByTestId('loan-status-amount-5') as HTMLInputElement).value).toBe(
      '1500000.00',
    )
    expect(screen.getByTestId('loan-status-form-hint-5')).toHaveTextContent(/update/i)
  })

  it('submits all three fields on Save and shows success', async () => {
    updateApplicationLoanMock.mockResolvedValue(SAVED_APPLICATION)
    const onSaved = vi.fn()
    render(
      <LoanStatusUpdateAction
        applicationId={5}
        initialLoan={EMPTY_LOAN}
        onSaved={onSaved}
      />,
      { wrapper },
    )

    await userEvent.type(screen.getByTestId('loan-status-status-5'), 'approved')
    await userEvent.type(screen.getByTestId('loan-status-lender-5'), 'HDFC Credila')
    await userEvent.type(screen.getByTestId('loan-status-amount-5'), '1500000')
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    await waitFor(() => {
      expect(updateApplicationLoanMock).toHaveBeenCalledTimes(1)
    })
    expect(updateApplicationLoanMock).toHaveBeenCalledWith(5, {
      loan_status: 'approved',
      loan_lender: 'HDFC Credila',
      loan_amount: '1500000',
    })
    expect(await screen.findByTestId('loan-status-success-5')).toBeInTheDocument()
    expect(onSaved).toHaveBeenCalledWith(5, SAVED_APPLICATION)
  })

  it('submits only the entered field for a partial update', async () => {
    updateApplicationLoanMock.mockResolvedValue({
      ...SAVED_APPLICATION,
      loan_status: 'disbursed',
    })
    render(
      <LoanStatusUpdateAction
        applicationId={5}
        initialLoan={{
          loan_status: 'approved',
          loan_lender: 'HDFC Credila',
          loan_amount: '1500000.00',
        }}
      />,
      { wrapper },
    )

    // Replace the status; leave lender + amount untouched.
    await userEvent.clear(screen.getByTestId('loan-status-status-5'))
    await userEvent.type(screen.getByTestId('loan-status-status-5'), 'disbursed')
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    await waitFor(() => {
      expect(updateApplicationLoanMock).toHaveBeenCalledTimes(1)
    })
    expect(updateApplicationLoanMock).toHaveBeenCalledWith(5, { loan_status: 'disbursed' })
  })

  it('submits an explicit null to clear a previously-recorded field', async () => {
    updateApplicationLoanMock.mockResolvedValue({
      ...SAVED_APPLICATION,
      loan_status: null,
    })
    render(
      <LoanStatusUpdateAction
        applicationId={5}
        initialLoan={{
          loan_status: 'approved',
          loan_lender: 'HDFC Credila',
          loan_amount: '1500000.00',
        }}
      />,
      { wrapper },
    )

    // Operator clears the status by deleting its contents.
    await userEvent.clear(screen.getByTestId('loan-status-status-5'))
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    await waitFor(() => {
      expect(updateApplicationLoanMock).toHaveBeenCalledTimes(1)
    })
    expect(updateApplicationLoanMock).toHaveBeenCalledWith(5, { loan_status: null })
  })

  it('trims surrounding whitespace on the status and lender', async () => {
    updateApplicationLoanMock.mockResolvedValue(SAVED_APPLICATION)
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} />,
      { wrapper },
    )

    await userEvent.type(screen.getByTestId('loan-status-status-5'), '  approved  ')
    await userEvent.type(screen.getByTestId('loan-status-lender-5'), '  HDFC Credila  ')
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    await waitFor(() => {
      expect(updateApplicationLoanMock).toHaveBeenCalledTimes(1)
    })
    expect(updateApplicationLoanMock).toHaveBeenCalledWith(
      5,
      expect.objectContaining({
        loan_status: 'approved',
        loan_lender: 'HDFC Credila',
      }),
    )
  })

  it('normalizes whitespace-only status to a clear (null)', async () => {
    updateApplicationLoanMock.mockResolvedValue(SAVED_APPLICATION)
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} />,
      { wrapper },
    )

    await userEvent.type(screen.getByTestId('loan-status-status-5'), '     ')
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    await waitFor(() => {
      expect(updateApplicationLoanMock).toHaveBeenCalledTimes(1)
    })
    expect(updateApplicationLoanMock).toHaveBeenCalledWith(5, { loan_status: null })
  })

  it('rejects a negative loan amount with a client-side validation error', async () => {
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} />,
      { wrapper },
    )

    // The native <input type="number" min="0"> would block submission in
    // some browsers but jsdom lets the submit through with an arbitrary
    // string, which is the path we want to exercise here: the form's
    // own JS validation should surface a user-readable message and
    // short-circuit the API call. We drive the controlled value via
    // the native ``change`` event the way a copy/paste would land it.
    await userEvent.type(screen.getByTestId('loan-status-status-5'), 'approved')
    const amountInput = screen.getByTestId('loan-status-amount-5') as HTMLInputElement
    await userEvent.click(amountInput)
    amountInput.value = '-100'
    amountInput.dispatchEvent(new Event('change', { bubbles: true }))
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    expect(
      await screen.findByTestId('loan-status-validation-5'),
    ).toHaveTextContent(/cannot be negative/i)
    expect(updateApplicationLoanMock).not.toHaveBeenCalled()
  })

  it('maps a 422 backend detail to a readable error and keeps the form open', async () => {
    updateApplicationLoanMock.mockRejectedValue(apiError(422, 'loan_status too long'))
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} />,
      { wrapper },
    )

    await userEvent.type(screen.getByTestId('loan-status-status-5'), 'approved')
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    expect(await screen.findByTestId('loan-status-error-5')).toHaveTextContent(
      /loan_status too long/i,
    )
    expect(screen.getByTestId('loan-status-form-5')).toBeInTheDocument()
  })

  it('maps a 403 backend detail to a permission-specific error', async () => {
    updateApplicationLoanMock.mockRejectedValue(apiError(403, 'Insufficient permissions'))
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} />,
      { wrapper },
    )

    await userEvent.type(screen.getByTestId('loan-status-status-5'), 'approved')
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    expect(await screen.findByTestId('loan-status-error-5')).toHaveTextContent(/permission/i)
  })

  it('maps a 401 backend detail to the session-expired copy', async () => {
    updateApplicationLoanMock.mockRejectedValue(apiError(401, 'Not authenticated'))
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} />,
      { wrapper },
    )

    await userEvent.type(screen.getByTestId('loan-status-status-5'), 'approved')
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    expect(await screen.findByTestId('loan-status-error-5')).toHaveTextContent(
      /session has expired/i,
    )
  })

  it('maps a 404 backend detail to the application-unavailable copy', async () => {
    updateApplicationLoanMock.mockRejectedValue(apiError(404, 'Application not found'))
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} />,
      { wrapper },
    )

    await userEvent.type(screen.getByTestId('loan-status-status-5'), 'approved')
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    expect(await screen.findByTestId('loan-status-error-5')).toHaveTextContent(
      /no longer available/i,
    )
  })

  it('maps a 500 backend detail to the generic failure copy', async () => {
    updateApplicationLoanMock.mockRejectedValue(apiError(500, 'Internal Server Error'))
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} />,
      { wrapper },
    )

    await userEvent.type(screen.getByTestId('loan-status-status-5'), 'approved')
    await userEvent.click(screen.getByTestId('loan-status-submit-5'))

    expect(await screen.findByTestId('loan-status-error-5')).toHaveTextContent(
      /failed to save the loan tracking fields/i,
    )
  })

  it('re-syncs the form when the initialLoan snapshot changes after a successful save', () => {
    updateApplicationLoanMock.mockResolvedValue(SAVED_APPLICATION)
    const { rerender } = render(
      <LoanStatusUpdateAction
        applicationId={5}
        initialLoan={{
          loan_status: 'in_progress',
          loan_lender: 'HDFC Credila',
          loan_amount: '1500000.00',
        }}
      />,
      { wrapper },
    )

    // The host updates its queue data source after a successful save.
    rerender(
      <AuthProvider>
        <LoanStatusUpdateAction
          applicationId={5}
          initialLoan={{
            loan_status: 'approved',
            loan_lender: 'SBI Scholar',
            loan_amount: '750000.00',
          }}
        />
      </AuthProvider>,
    )

    expect((screen.getByTestId('loan-status-status-5') as HTMLInputElement).value).toBe(
      'approved',
    )
    expect((screen.getByTestId('loan-status-lender-5') as HTMLInputElement).value).toBe(
      'SBI Scholar',
    )
    expect((screen.getByTestId('loan-status-amount-5') as HTMLInputElement).value).toBe(
      '750000.00',
    )
  })

  it('resets the form when the Clear button is clicked', async () => {
    render(
      <LoanStatusUpdateAction
        applicationId={5}
        initialLoan={{
          loan_status: 'approved',
          loan_lender: 'HDFC Credila',
          loan_amount: '1500000.00',
        }}
      />,
      { wrapper },
    )

    await userEvent.click(screen.getByTestId('loan-status-clear-5'))

    expect((screen.getByTestId('loan-status-status-5') as HTMLInputElement).value).toBe('')
    expect((screen.getByTestId('loan-status-lender-5') as HTMLInputElement).value).toBe('')
    expect((screen.getByTestId('loan-status-amount-5') as HTMLInputElement).value).toBe('')
  })

  it('renders a read-only summary with the recorded fields when readOnly is true', () => {
    render(
      <LoanStatusUpdateAction
        applicationId={5}
        initialLoan={{
          loan_status: 'approved',
          loan_lender: 'HDFC Credila',
          loan_amount: '1500000.00',
        }}
        readOnly
      />,
      { wrapper },
    )

    expect(screen.getByTestId('loan-status-readonly-5')).toBeInTheDocument()
    expect(screen.getByTestId('loan-status-readonly-status-5')).toHaveTextContent('approved')
    expect(screen.getByTestId('loan-status-readonly-lender-5')).toHaveTextContent('HDFC Credila')
    // The amount is rendered currency-aware; the placeholder testid
    // confirms the span exists, and we assert it carries *some*
    // formatted content (the exact locale form varies).
    const amount = screen.getByTestId('loan-status-readonly-amount-5')
    expect(amount.textContent).not.toBe('')
    expect(screen.queryByTestId('loan-status-submit-5')).not.toBeInTheDocument()
  })

  it('renders the read-only placeholder when no loan fields are recorded yet', () => {
    render(
      <LoanStatusUpdateAction applicationId={5} initialLoan={EMPTY_LOAN} readOnly />,
      { wrapper },
    )

    expect(screen.getByTestId('loan-status-readonly-5')).toBeInTheDocument()
    expect(screen.getByTestId('loan-status-readonly-status-5')).toHaveTextContent('—')
    expect(screen.getByTestId('loan-status-readonly-lender-5')).toHaveTextContent('—')
    expect(screen.getByTestId('loan-status-readonly-amount-5')).toHaveTextContent('—')
  })
})

describe('LoanStatusUpdateAction amount-input parser', () => {
  it('returns null with no error for an empty / whitespace-only input', () => {
    expect(__testing.parseLoanAmountInput('')).toEqual({ value: null, error: null })
    expect(__testing.parseLoanAmountInput('   ')).toEqual({ value: null, error: null })
  })

  it('returns the trimmed string for a plain integer / decimal', () => {
    expect(__testing.parseLoanAmountInput('1500000')).toEqual({
      value: '1500000',
      error: null,
    })
    expect(__testing.parseLoanAmountInput('1500000.50')).toEqual({
      value: '1500000.50',
      error: null,
    })
    expect(__testing.parseLoanAmountInput('  1500000.50  ')).toEqual({
      value: '1500000.50',
      error: null,
    })
    expect(__testing.parseLoanAmountInput('0')).toEqual({ value: '0', error: null })
  })

  it('rejects a negative amount with a user-readable error', () => {
    const result = __testing.parseLoanAmountInput('-100')
    expect(result.value).toBeNull()
    expect(result.error).toMatch(/cannot be negative/i)
  })

  it('rejects a non-numeric input with a user-readable error', () => {
    const result = __testing.parseLoanAmountInput('abc')
    expect(result.value).toBeNull()
    expect(result.error).toMatch(/non-negative number/i)
  })
})

describe('LoanStatusUpdateAction read-only amount formatter', () => {
  it('renders the em-dash placeholder when the amount is null', () => {
    expect(__testing.renderReadOnlyLoanAmount(null, 'INR')).toBe('—')
  })

  it('renders a currency-aware string when the code is in the curated set', () => {
    const display = __testing.renderReadOnlyLoanAmount('1500000.00', 'INR')
    // The exact locale formatting depends on the test runner's
    // environment (Indian vs. Western grouping); we only assert the
    // digits survive intact and the ISO 4217 code is appended.
    expect(display).toMatch(/1500000|15,00,000|1,500,000/)
    expect(display).toContain('INR')
  })

  it('falls back to a plain numeric rendering when the code is invalid', () => {
    const display = __testing.renderReadOnlyLoanAmount('1500000.00', 'not-a-code')
    // No currency code prefix is appended in the fallback path.
    expect(display).not.toMatch(/not-a-code/)
    expect(display).toMatch(/1500000|15,00,000|1,500,000/)
  })
})
