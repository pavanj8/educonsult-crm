import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as applicationsApi from '../../api/applications'
import type { Application } from '../../types/application'

import LoanOptInAction from './LoanOptInAction'

vi.mock('../../api/applications', () => ({ setLoanOptIn: vi.fn() }))
const setLoanOptInMock = vi.mocked(applicationsApi.setLoanOptIn)

function apiError(status: number, message: string): Error {
  return Object.assign(new Error(message), { name: 'ApiError', status })
}

describe('LoanOptInAction', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders the not-opted-in status and a toggle button to opt in', () => {
    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveTextContent('Not opted in')
    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveAttribute(
      'data-loan-opt-in',
      'false',
    )
    expect(screen.getByTestId('loan-opt-in-toggle-42')).toHaveTextContent(
      'Opt in to loan tracking',
    )
  })

  it('renders the opted-in status and a toggle button to opt out', () => {
    render(<LoanOptInAction applicationId={42} loanOptIn={true} />)

    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveTextContent('Opted in')
    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveAttribute(
      'data-loan-opt-in',
      'true',
    )
    expect(screen.getByTestId('loan-opt-in-toggle-42')).toHaveTextContent(
      'Opt out of loan tracking',
    )
  })

  it('patches loan_opt_in=true when the student opts in, updates the UI to reflect the new state, and notifies the host', async () => {
    const user = userEvent.setup()
    const onChanged = vi.fn()
    setLoanOptInMock.mockResolvedValue({
      id: 42,
      tenant_id: 10,
      student_id: 7,
      university_id: 1,
      program_id: 10,
      stage: 'registered',
      loan_opt_in: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-02T00:00:00Z',
    } as never)

    render(<LoanOptInAction applicationId={42} loanOptIn={false} onChanged={onChanged} />)

    // Initial state: not opted in
    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveTextContent('Not opted in')
    expect(screen.getByTestId('loan-opt-in-toggle-42')).toHaveTextContent(
      'Opt in to loan tracking',
    )

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(setLoanOptInMock).toHaveBeenCalledWith(42, true)

    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledWith(42, true)
    })

    // After successful toggle, the UI reflects the new state
    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveTextContent('Opted in')
    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveAttribute(
      'data-loan-opt-in',
      'true',
    )
    expect(screen.getByTestId('loan-opt-in-toggle-42')).toHaveTextContent(
      'Opt out of loan tracking',
    )

    expect(screen.queryByTestId('loan-opt-in-error-42')).not.toBeInTheDocument()
  })

  it('calls onChanged callback with the new loan opt-in value after successful toggle', async () => {
    const user = userEvent.setup()
    const onChanged = vi.fn()
    setLoanOptInMock.mockResolvedValue({
      id: 42,
      tenant_id: 10,
      student_id: 7,
      university_id: 1,
      program_id: 10,
      stage: 'registered',
      loan_opt_in: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-02T00:00:00Z',
    } as never)

    const { rerender } = render(
      <LoanOptInAction applicationId={42} loanOptIn={false} onChanged={onChanged} />,
    )

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledWith(42, true)
    })

    // Simulate parent re-rendering with updated prop
    rerender(<LoanOptInAction applicationId={42} loanOptIn={true} onChanged={onChanged} />)

    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveTextContent('Opted in')
    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveAttribute(
      'data-loan-opt-in',
      'true',
    )
    expect(screen.getByTestId('loan-opt-in-toggle-42')).toHaveTextContent(
      'Opt out of loan tracking',
    )
  })

  it('patches loan_opt_in=false when the student opts out, updates the UI to reflect the new state, and notifies the host', async () => {
    const user = userEvent.setup()
    const onChanged = vi.fn()
    setLoanOptInMock.mockResolvedValue({
      id: 42,
      tenant_id: 10,
      student_id: 7,
      university_id: 1,
      program_id: 10,
      stage: 'registered',
      loan_opt_in: false,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-02T00:00:00Z',
    } as never)

    render(<LoanOptInAction applicationId={42} loanOptIn={true} onChanged={onChanged} />)

    // Initial state: opted in
    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveTextContent('Opted in')
    expect(screen.getByTestId('loan-opt-in-toggle-42')).toHaveTextContent(
      'Opt out of loan tracking',
    )

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(setLoanOptInMock).toHaveBeenCalledWith(42, false)

    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledWith(42, false)
    })

    // After successful toggle, the UI reflects the new state
    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveTextContent('Not opted in')
    expect(screen.getByTestId('loan-opt-in-status-42')).toHaveAttribute(
      'data-loan-opt-in',
      'false',
    )
    expect(screen.getByTestId('loan-opt-in-toggle-42')).toHaveTextContent(
      'Opt in to loan tracking',
    )
  })

  it('disables the toggle while the PATCH request is in flight', async () => {
    const user = userEvent.setup()
    let resolveFetch: (value: Application) => void = () => {
      throw new Error('resolveFetch not set')
    }
    setLoanOptInMock.mockImplementation(
      () =>
        new Promise<Application>((resolve) => {
          resolveFetch = resolve
        }),
    )

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    const toggle = screen.getByTestId('loan-opt-in-toggle-42')
    await user.click(toggle)

    expect(toggle).toBeDisabled()
    expect(toggle).toHaveAttribute('aria-busy', 'true')
    expect(toggle).toHaveTextContent('Saving…')

    resolveFetch({
      id: 42,
      loan_opt_in: true,
    } as Application)

    await waitFor(() => {
      expect(toggle).not.toBeDisabled()
    })
  })

  it('surfaces a readable error when the API rejects with 404 (endpoint not yet wired)', async () => {
    const user = userEvent.setup()
    setLoanOptInMock.mockRejectedValue(apiError(404, 'Application not found'))

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(await screen.findByTestId('loan-opt-in-error-42')).toHaveTextContent(
      'This application is no longer available',
    )
  })

  it('surfaces a readable error when the API rejects with 403', async () => {
    const user = userEvent.setup()
    setLoanOptInMock.mockRejectedValue(apiError(403, 'Insufficient permissions'))

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(await screen.findByTestId('loan-opt-in-error-42')).toHaveTextContent(
      "You don't have permission to update this application",
    )
  })

  it('surfaces a readable error when the API rejects with 401', async () => {
    const user = userEvent.setup()
    setLoanOptInMock.mockRejectedValue(apiError(401, 'Not authenticated'))

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(await screen.findByTestId('loan-opt-in-error-42')).toHaveTextContent(
      'Your session has expired — please sign in again',
    )
  })

  it('surfaces a readable error when the network call rejects', async () => {
    const user = userEvent.setup()
    setLoanOptInMock.mockRejectedValue(new Error('network down'))

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(await screen.findByTestId('loan-opt-in-error-42')).toHaveTextContent(
      'Failed to update the loan-tracking preference',
    )
  })

  it('clears the previous error when a follow-up toggle succeeds', async () => {
    const user = userEvent.setup()
    setLoanOptInMock
      .mockRejectedValueOnce(apiError(500, 'Internal server error'))
      .mockResolvedValueOnce({ id: 42, loan_opt_in: true } as Application)

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))
    expect(await screen.findByTestId('loan-opt-in-error-42')).toBeInTheDocument()

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    await waitFor(() => {
      expect(screen.queryByTestId('loan-opt-in-error-42')).not.toBeInTheDocument()
    })
  })
})
