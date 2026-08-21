import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ApproveAction from './ApproveAction'

function renderAction(onApprove = vi.fn().mockResolvedValue(undefined)) {
  render(<ApproveAction documentId={7} documentLabel="passport.pdf" onApprove={onApprove} />)
  return onApprove
}

describe('ApproveAction', () => {
  it('opens the approve form when the Approve button is clicked', async () => {
    renderAction()
    await userEvent.click(screen.getByTestId('approve-open-7'))
    expect(screen.getByTestId('approve-form-7')).toBeInTheDocument()
  })

  it('approves with the optional comment', async () => {
    const onApprove = renderAction()
    await userEvent.click(screen.getByTestId('approve-open-7'))
    await userEvent.type(screen.getByTestId('approve-comment-7'), 'Looks good')
    await userEvent.click(screen.getByTestId('approve-submit-7'))
    expect(onApprove).toHaveBeenCalledWith(7, 'Looks good')
  })

  it('approves with no comment (optional)', async () => {
    const onApprove = renderAction()
    await userEvent.click(screen.getByTestId('approve-open-7'))
    await userEvent.click(screen.getByTestId('approve-submit-7'))
    expect(onApprove).toHaveBeenCalledWith(7, '')
  })

  it('shows the error and keeps the form open when approve fails', async () => {
    const onApprove = vi.fn().mockRejectedValue(new Error('This document is no longer available'))
    renderAction(onApprove)
    await userEvent.click(screen.getByTestId('approve-open-7'))
    await userEvent.click(screen.getByTestId('approve-submit-7'))
    expect(await screen.findByTestId('approve-error-7')).toHaveTextContent(/no longer available/i)
    expect(screen.getByTestId('approve-form-7')).toBeInTheDocument()
  })
})
