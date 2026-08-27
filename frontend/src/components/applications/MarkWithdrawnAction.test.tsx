import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MarkWithdrawnAction from './MarkWithdrawnAction'
import { markWithdrawn } from '../../api/applications'

vi.mock('../../api/applications', () => ({ markWithdrawn: vi.fn() }))
const markWithdrawnMock = vi.mocked(markWithdrawn)

function apiError(status: number, message: string): Error {
  return Object.assign(new Error(message), { name: 'ApiError', status })
}

describe('MarkWithdrawnAction', () => {
  beforeEach(() => vi.clearAllMocks())

  it('opens the form with a required reason field', async () => {
    render(<MarkWithdrawnAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('mark-withdrawn-open-5'))
    const textarea = screen.getByTestId('mark-withdrawn-reason-5')
    expect(textarea).toHaveAttribute('aria-required', 'true')
    expect(textarea).toHaveAttribute('maxlength', '2000')
  })

  it('blocks submit and shows a validation error when the reason is empty', async () => {
    render(<MarkWithdrawnAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('mark-withdrawn-open-5'))
    // Bypass native HTML validation to exercise our JS-side guard.
    const form = screen.getByTestId('mark-withdrawn-form-5') as HTMLFormElement
    form.noValidate = true
    await userEvent.click(screen.getByTestId('mark-withdrawn-submit-5'))
    expect(screen.getByTestId('mark-withdrawn-validation-5')).toHaveTextContent(/required/i)
    expect(markWithdrawnMock).not.toHaveBeenCalled()
  })

  it('marks withdrawn with the trimmed reason and shows success', async () => {
    markWithdrawnMock.mockResolvedValue({} as never)
    const onWithdrawn = vi.fn()
    render(<MarkWithdrawnAction applicationId={5} onWithdrawn={onWithdrawn} />)
    await userEvent.click(screen.getByTestId('mark-withdrawn-open-5'))
    await userEvent.type(screen.getByTestId('mark-withdrawn-reason-5'), '  Missing documents  ')
    await userEvent.click(screen.getByTestId('mark-withdrawn-submit-5'))
    expect(markWithdrawnMock).toHaveBeenCalledWith(5, 'Missing documents')
    expect(await screen.findByTestId('mark-withdrawn-success-5')).toBeInTheDocument()
    expect(onWithdrawn).toHaveBeenCalledWith(5)
  })

  it('shows a mapped error and keeps the form open on 422', async () => {
    markWithdrawnMock.mockRejectedValue(apiError(422, 'bad stage'))
    render(<MarkWithdrawnAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('mark-withdrawn-open-5'))
    await userEvent.type(screen.getByTestId('mark-withdrawn-reason-5'), 'why')
    await userEvent.click(screen.getByTestId('mark-withdrawn-submit-5'))
    expect(await screen.findByTestId('mark-withdrawn-error-5')).toHaveTextContent(/cannot be withdrawn|bad stage/i)
    expect(screen.getByTestId('mark-withdrawn-form-5')).toBeInTheDocument()
  })
})
