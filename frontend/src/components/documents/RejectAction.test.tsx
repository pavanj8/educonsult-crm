import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import RejectAction from './RejectAction'

function renderAction(onReject = vi.fn().mockResolvedValue(undefined)) {
  render(<RejectAction documentId={7} documentLabel="passport.pdf" onReject={onReject} />)
  return onReject
}

describe('RejectAction', () => {
  it('opens the reject form when the Reject button is clicked', async () => {
    renderAction()
    await userEvent.click(screen.getByTestId('reject-open-7'))
    expect(screen.getByTestId('reject-form-7')).toBeInTheDocument()
    const textarea = screen.getByTestId('reject-comment-7')
    expect(textarea).toHaveAttribute('aria-required', 'true')
    expect(textarea).toHaveAttribute('maxlength', '2000')
  })

  it('blocks submit and shows a validation error when the comment is empty', async () => {
    const onReject = renderAction()
    await userEvent.click(screen.getByTestId('reject-open-7'))
    // Bypass native HTML validation to exercise our JS-side guard.
    const form = screen.getByTestId('reject-form-7') as HTMLFormElement
    form.noValidate = true
    await userEvent.click(screen.getByTestId('reject-submit-7'))

    expect(screen.getByTestId('reject-validation-7')).toHaveTextContent(/required/i)
    expect(onReject).not.toHaveBeenCalled()
  })

  it('submits the trimmed comment and calls onReject', async () => {
    const onReject = renderAction()
    await userEvent.click(screen.getByTestId('reject-open-7'))
    await userEvent.type(screen.getByTestId('reject-comment-7'), '  Not legible  ')
    await userEvent.click(screen.getByTestId('reject-submit-7'))

    expect(onReject).toHaveBeenCalledWith(7, 'Not legible')
  })

  it('keeps the form open and shows the error when onReject fails', async () => {
    const onReject = vi.fn().mockRejectedValue(new Error('This document is no longer available'))
    renderAction(onReject)
    await userEvent.click(screen.getByTestId('reject-open-7'))
    await userEvent.type(screen.getByTestId('reject-comment-7'), 'Blurry scan')
    await userEvent.click(screen.getByTestId('reject-submit-7'))

    expect(await screen.findByTestId('reject-error-7')).toHaveTextContent(/no longer available/i)
    expect(screen.getByTestId('reject-form-7')).toBeInTheDocument()
  })

  it('updates the character counter as the verifier types', async () => {
    renderAction()
    await userEvent.click(screen.getByTestId('reject-open-7'))
    await userEvent.type(screen.getByTestId('reject-comment-7'), 'abc')
    expect(screen.getByTestId('reject-counter-7')).toHaveTextContent('1997 characters remaining')
  })
})
