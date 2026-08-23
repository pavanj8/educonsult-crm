import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ReassignCounselorAction, {
  type ReassignCounselorOption,
} from './ReassignCounselorAction'
import { reassignCounselor } from '../../api/applications'

vi.mock('../../api/applications', () => ({ reassignCounselor: vi.fn() }))
const reassignCounselorMock = vi.mocked(reassignCounselor)

const counselors: ReassignCounselorOption[] = [
  { id: 11, email: 'alice@demo.test', is_active: true },
  { id: 12, email: 'bob@demo.test', is_active: true },
  { id: 13, email: 'inactive@demo.test', is_active: false },
]

function apiError(status: number, message: string): Error {
  return Object.assign(new Error(message), { name: 'ApiError', status })
}

describe('ReassignCounselorAction', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the current assigned counselor email in summary mode', () => {
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={11}
        availableCounselors={counselors}
      />,
    )

    expect(screen.getByTestId('reassign-counselor-current-5')).toHaveTextContent('alice@demo.test')
    expect(screen.getByTestId('reassign-counselor-open-5')).toBeInTheDocument()
  })

  it('renders "Unassigned" when no counselor is currently assigned', () => {
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={null}
        availableCounselors={counselors}
      />,
    )

    expect(screen.getByTestId('reassign-counselor-current-5')).toHaveTextContent('Unassigned')
  })

  it('falls back to a numeric label when the current counselor is not in the supplied list', () => {
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={99}
        availableCounselors={counselors}
      />,
    )

    expect(screen.getByTestId('reassign-counselor-current-5')).toHaveTextContent('Counselor #99')
  })

  it('opens the form pre-selected with the current counselor', async () => {
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={12}
        availableCounselors={counselors}
      />,
    )

    await userEvent.click(screen.getByTestId('reassign-counselor-open-5'))

    const select = screen.getByTestId('reassign-counselor-select-5') as HTMLSelectElement
    expect(select.value).toBe('12')
  })

  it('only lists active counselors plus an Unassigned option', async () => {
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={11}
        availableCounselors={counselors}
      />,
    )

    await userEvent.click(screen.getByTestId('reassign-counselor-open-5'))

    const select = screen.getByTestId('reassign-counselor-select-5') as HTMLSelectElement
    const optionLabels = Array.from(select.options).map((opt) => opt.text)
    expect(optionLabels).toEqual([
      'Unassigned',
      'alice@demo.test',
      'bob@demo.test',
    ])
  })

  it('submits a picked counselor id and reports success', async () => {
    reassignCounselorMock.mockResolvedValue({} as never)
    const onReassigned = vi.fn()
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={11}
        availableCounselors={counselors}
        onReassigned={onReassigned}
      />,
    )

    await userEvent.click(screen.getByTestId('reassign-counselor-open-5'))
    await userEvent.selectOptions(screen.getByTestId('reassign-counselor-select-5'), '12')
    await userEvent.click(screen.getByTestId('reassign-counselor-submit-5'))

    expect(reassignCounselorMock).toHaveBeenCalledWith(5, 12)
    expect(await screen.findByTestId('reassign-counselor-success-5')).toBeInTheDocument()
    expect(onReassigned).toHaveBeenCalledWith(5, 12)
  })

  it('submits the unassign choice (null) when the operator picks Unassigned', async () => {
    reassignCounselorMock.mockResolvedValue({} as never)
    const onReassigned = vi.fn()
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={11}
        availableCounselors={counselors}
        onReassigned={onReassigned}
      />,
    )

    await userEvent.click(screen.getByTestId('reassign-counselor-open-5'))
    await userEvent.selectOptions(screen.getByTestId('reassign-counselor-select-5'), '')
    await userEvent.click(screen.getByTestId('reassign-counselor-submit-5'))

    expect(reassignCounselorMock).toHaveBeenCalledWith(5, null)
    expect(await screen.findByTestId('reassign-counselor-success-5')).toBeInTheDocument()
    expect(onReassigned).toHaveBeenCalledWith(5, null)
  })

  it('maps a 422 backend detail to a readable error and keeps the form open', async () => {
    reassignCounselorMock.mockRejectedValue(apiError(422, 'Target counselor not found'))
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={11}
        availableCounselors={counselors}
      />,
    )

    await userEvent.click(screen.getByTestId('reassign-counselor-open-5'))
    await userEvent.selectOptions(screen.getByTestId('reassign-counselor-select-5'), '12')
    await userEvent.click(screen.getByTestId('reassign-counselor-submit-5'))

    expect(await screen.findByTestId('reassign-counselor-error-5')).toHaveTextContent(
      /Target counselor not found/i,
    )
    expect(screen.getByTestId('reassign-counselor-form-5')).toBeInTheDocument()
  })

  it('maps a 403 backend detail to a permission-specific error', async () => {
    reassignCounselorMock.mockRejectedValue(apiError(403, 'Insufficient permissions'))
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={11}
        availableCounselors={counselors}
      />,
    )

    await userEvent.click(screen.getByTestId('reassign-counselor-open-5'))
    await userEvent.selectOptions(screen.getByTestId('reassign-counselor-select-5'), '12')
    await userEvent.click(screen.getByTestId('reassign-counselor-submit-5'))

    expect(await screen.findByTestId('reassign-counselor-error-5')).toHaveTextContent(
      /permission/i,
    )
  })

  it('cancel closes the form without calling the API', async () => {
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={11}
        availableCounselors={counselors}
      />,
    )

    await userEvent.click(screen.getByTestId('reassign-counselor-open-5'))
    await userEvent.click(screen.getByTestId('reassign-counselor-cancel-5'))

    expect(reassignCounselorMock).not.toHaveBeenCalled()
    expect(screen.queryByTestId('reassign-counselor-form-5')).not.toBeInTheDocument()
    // After cancel we drop back to summary mode with the open button.
    expect(screen.getByTestId('reassign-counselor-open-5')).toBeInTheDocument()
  })

  it('readOnly mode hides the reassignment controls and shows only the current assignment', () => {
    render(
      <ReassignCounselorAction
        applicationId={5}
        currentCounselorId={11}
        availableCounselors={counselors}
        readOnly
      />,
    )

    expect(screen.getByTestId('reassign-counselor-current-5')).toHaveTextContent('alice@demo.test')
    expect(screen.queryByTestId('reassign-counselor-open-5')).not.toBeInTheDocument()
    expect(screen.queryByTestId('reassign-counselor-form-5')).not.toBeInTheDocument()
  })
})
