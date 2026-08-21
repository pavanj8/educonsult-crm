import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MarkRejectedAction from './MarkRejectedAction'
import { markRejected } from '../../api/applications'

vi.mock('../../api/applications', () => ({ markRejected: vi.fn() }))
const markRejectedMock = vi.mocked(markRejected)

function apiError(status: number, message: string): Error {
  return Object.assign(new Error(message), { name: 'ApiError', status })
}

describe('MarkRejectedAction', () => {
  beforeEach(() => vi.clearAllMocks())

  it('opens the form with a required reason field', async () => {
    render(<MarkRejectedAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('mark-rejected-open-5'))
    const textarea = screen.getByTestId('mark-rejected-reason-5')
    expect(textarea).toHaveAttribute('aria-required', 'true')
    expect(textarea).toHaveAttribute('maxlength', '2000')
  })

  it('blocks submit and shows a validation error when the reason is empty', async () => {
    render(<MarkRejectedAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('mark-rejected-open-5'))
    await userEvent.click(screen.getByTestId('mark-rejected-submit-5'))
    expect(screen.getByTestId('mark-rejected-validation-5')).toHaveTextContent(/required/i)
    expect(markRejectedMock).not.toHaveBeenCalled()
  })

  it('marks rejected with the trimmed reason and shows success', async () => {
    markRejectedMock.mockResolvedValue({} as never)
    const onRejected = vi.fn()
    render(<MarkRejectedAction applicationId={5} onRejected={onRejected} />)
    await userEvent.click(screen.getByTestId('mark-rejected-open-5'))
    await userEvent.type(screen.getByTestId('mark-rejected-reason-5'), '  Missing documents  ')
    await userEvent.click(screen.getByTestId('mark-rejected-submit-5'))
    expect(markRejectedMock).toHaveBeenCalledWith(5, 'Missing documents')
    expect(await screen.findByTestId('mark-rejected-success-5')).toBeInTheDocument()
    expect(onRejected).toHaveBeenCalledWith(5)
  })

  it('shows a mapped error and keeps the form open on 422', async () => {
    markRejectedMock.mockRejectedValue(apiError(422, 'bad stage'))
    render(<MarkRejectedAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('mark-rejected-open-5'))
    await userEvent.type(screen.getByTestId('mark-rejected-reason-5'), 'why')
    await userEvent.click(screen.getByTestId('mark-rejected-submit-5'))
    expect(await screen.findByTestId('mark-rejected-error-5')).toHaveTextContent(/cannot be rejected|bad stage/i)
    expect(screen.getByTestId('mark-rejected-form-5')).toBeInTheDocument()
  })
})
