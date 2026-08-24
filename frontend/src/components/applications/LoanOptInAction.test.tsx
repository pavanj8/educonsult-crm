import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import LoanOptInAction from './LoanOptInAction'

describe('LoanOptInAction', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    localStorage.setItem('access_token', 'test-token')
  })

  afterEach(() => {
    vi.restoreAllMocks()
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

  it('patches loan_opt_in=true when the student opts in and notifies the host', async () => {
    const user = userEvent.setup()
    const onChanged = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: 42,
        tenant_id: 10,
        student_id: 7,
        university_id: 1,
        program_id: 10,
        stage: 'registered',
        loan_opt_in: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<LoanOptInAction applicationId={42} loanOptIn={false} onChanged={onChanged} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/applications/42/loan-opt-in',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ loan_opt_in: true }),
        }),
      )
    })

    const headers = (fetchMock.mock.calls[0]?.[1]?.headers ?? {}) as Record<string, string>
    expect(headers.Authorization).toBe('Bearer test-token')
    expect(headers['Content-Type']).toBe('application/json')

    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledWith(42, true)
    })

    expect(screen.queryByTestId('loan-opt-in-error-42')).not.toBeInTheDocument()
  })

  it('patches loan_opt_in=false when the student opts out and notifies the host', async () => {
    const user = userEvent.setup()
    const onChanged = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: 42,
        tenant_id: 10,
        student_id: 7,
        university_id: 1,
        program_id: 10,
        stage: 'registered',
        loan_opt_in: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<LoanOptInAction applicationId={42} loanOptIn={true} onChanged={onChanged} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/applications/42/loan-opt-in',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ loan_opt_in: false }),
        }),
      )
    })

    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledWith(42, false)
    })
  })

  it('disables the toggle while the PATCH request is in flight', async () => {
    const user = userEvent.setup()
    let resolveFetch: (value: Response) => void = () => {
      throw new Error('resolveFetch not set')
    }
    const fetchMock = vi.fn().mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve
        }),
    )
    globalThis.fetch = fetchMock as typeof fetch

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    const toggle = screen.getByTestId('loan-opt-in-toggle-42')
    await user.click(toggle)

    expect(toggle).toBeDisabled()
    expect(toggle).toHaveAttribute('aria-busy', 'true')
    expect(toggle).toHaveTextContent('Saving…')

    resolveFetch({
      ok: true,
      status: 200,
      json: async () => ({
        id: 42,
        loan_opt_in: true,
      }),
    } as Response)

    await waitFor(() => {
      expect(toggle).not.toBeDisabled()
    })
  })

  it('surfaces a readable error when the API rejects with 404 (endpoint not yet wired)', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Application not found' }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(await screen.findByTestId('loan-opt-in-error-42')).toHaveTextContent(
      'This application is no longer available',
    )
  })

  it('surfaces a readable error when the API rejects with 403', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(await screen.findByTestId('loan-opt-in-error-42')).toHaveTextContent(
      "You don't have permission to update this application",
    )
  })

  it('surfaces a readable error when the API rejects with 401', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Not authenticated' }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(await screen.findByTestId('loan-opt-in-error-42')).toHaveTextContent(
      'Your session has expired — please sign in again',
    )
  })

  it('surfaces a readable error when the network call rejects', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockRejectedValue(new Error('network down'))
    globalThis.fetch = fetchMock as typeof fetch

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    expect(await screen.findByTestId('loan-opt-in-error-42')).toHaveTextContent(
      'Failed to update the loan-tracking preference',
    )
  })

  it('clears the previous error when a follow-up toggle succeeds', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Internal server error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 42, loan_opt_in: true }),
      })
    globalThis.fetch = fetchMock as typeof fetch

    render(<LoanOptInAction applicationId={42} loanOptIn={false} />)

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))
    expect(await screen.findByTestId('loan-opt-in-error-42')).toBeInTheDocument()

    await user.click(screen.getByTestId('loan-opt-in-toggle-42'))

    await waitFor(() => {
      expect(screen.queryByTestId('loan-opt-in-error-42')).not.toBeInTheDocument()
    })
  })
})
