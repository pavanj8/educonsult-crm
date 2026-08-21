import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MarkEnrolledAction from './MarkEnrolledAction'
import { markEnrolled } from '../../api/applications'

vi.mock('../../api/applications', () => ({ markEnrolled: vi.fn() }))
const markEnrolledMock = vi.mocked(markEnrolled)

function apiError(status: number, message: string): Error {
  return Object.assign(new Error(message), { name: 'ApiError', status })
}

describe('MarkEnrolledAction', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('opens the form when the Mark enrolled button is clicked', async () => {
    render(<MarkEnrolledAction applicationId={5} />)
    await userEvent.click(screen.getByTestId('mark-enrolled-open-5'))
    expect(screen.getByTestId('mark-enrolled-form-5')).toBeInTheDocument()
  })

  it('marks enrolled with the entered details and shows success', async () => {
    markEnrolledMock.mockResolvedValue({} as never)
    const onEnrolled = vi.fn()
    render(<MarkEnrolledAction applicationId={5} onEnrolled={onEnrolled} />)

    await userEvent.click(screen.getByTestId('mark-enrolled-open-5'))
    await userEvent.type(screen.getByTestId('mark-enrolled-details-5'), 'Fall 2026 intake')
    await userEvent.click(screen.getByTestId('mark-enrolled-submit-5'))

    expect(markEnrolledMock).toHaveBeenCalledWith(5, 'Fall 2026 intake')
    expect(await screen.findByTestId('mark-enrolled-success-5')).toBeInTheDocument()
    expect(onEnrolled).toHaveBeenCalledWith(5)
  })

  it('allows enrolment with no details (optional)', async () => {
    markEnrolledMock.mockResolvedValue({} as never)
    render(<MarkEnrolledAction applicationId={5} />)

    await userEvent.click(screen.getByTestId('mark-enrolled-open-5'))
    await userEvent.click(screen.getByTestId('mark-enrolled-submit-5'))

    expect(markEnrolledMock).toHaveBeenCalledWith(5, '')
    expect(await screen.findByTestId('mark-enrolled-success-5')).toBeInTheDocument()
  })

  it('shows a mapped error and keeps the form open when the API rejects (422)', async () => {
    markEnrolledMock.mockRejectedValue(apiError(422, 'bad stage'))
    render(<MarkEnrolledAction applicationId={5} />)

    await userEvent.click(screen.getByTestId('mark-enrolled-open-5'))
    await userEvent.click(screen.getByTestId('mark-enrolled-submit-5'))

    expect(await screen.findByTestId('mark-enrolled-error-5')).toHaveTextContent(/cannot be marked enrolled|bad stage/i)
    expect(screen.getByTestId('mark-enrolled-form-5')).toBeInTheDocument()
  })
})
