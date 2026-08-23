import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AddNoteForm from './AddNoteForm'

describe('AddNoteForm', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the "Add note" button by default', () => {
    render(<AddNoteForm applicationId={5} studentId={42} />)
    expect(screen.getByTestId('add-note-open-5')).toBeInTheDocument()
  })

  it('opens the form pre-populated with an empty body', async () => {
    render(<AddNoteForm applicationId={5} studentId={42} />)
    await userEvent.click(screen.getByTestId('add-note-open-5'))
    expect(screen.getByTestId('add-note-form-5')).toBeInTheDocument()
    const bodyArea = screen.getByTestId('add-note-body-5') as HTMLTextAreaElement
    expect(bodyArea.value).toBe('')
  })

  it('submit empty form rejects before hitting the API', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch
    render(<AddNoteForm applicationId={5} studentId={42} />)
    await userEvent.click(screen.getByTestId('add-note-open-5'))
    // Bypass native HTML validation to exercise our JS-side guard.
    const form = screen.getByTestId('add-note-form-5') as HTMLFormElement
    form.noValidate = true
    await userEvent.click(screen.getByTestId('add-note-submit-5'))

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByTestId('add-note-error-5')).toHaveTextContent(
      /write something/i,
    )
  })

  it('submits the body via the API and closes the form on success', async () => {
    const created = {
      id: 99,
      tenant_id: 10,
      student_id: 42,
      application_id: 5,
      author_user_id: 7,
      body: 'Quick counseling note.',
      created_at: '2026-04-01T09:00:00Z',
      updated_at: '2026-04-01T09:00:00Z',
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => created,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const onCreated = vi.fn()
    render(<AddNoteForm applicationId={5} studentId={42} onCreated={onCreated} />)
    await userEvent.click(screen.getByTestId('add-note-open-5'))
    await userEvent.type(
      screen.getByTestId('add-note-body-5'),
      '  Quick counseling note.  ',
    )
    await userEvent.click(screen.getByTestId('add-note-submit-5'))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [calledUrl, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined]
    expect(calledUrl).toContain('/notes')
    expect(init?.method).toBe('POST')
    const body = JSON.parse((init?.body ?? '{}') as string)
    expect(body).toEqual({
      student_id: 42,
      application_id: 5,
      body: 'Quick counseling note.',
    })

    // Form should close after success.
    expect(screen.queryByTestId('add-note-form-5')).not.toBeInTheDocument()
    expect(screen.getByTestId('add-note-open-5')).toBeInTheDocument()
    expect(onCreated).toHaveBeenCalledTimes(1)
  })

  it('maps a 422 backend detail to a readable error and keeps the form open', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'body must not be blank' }),
    }) as typeof fetch

    render(<AddNoteForm applicationId={5} studentId={42} />)
    await userEvent.click(screen.getByTestId('add-note-open-5'))
    await userEvent.type(screen.getByTestId('add-note-body-5'), 'Test note.')
    await userEvent.click(screen.getByTestId('add-note-submit-5'))

    expect(await screen.findByTestId('add-note-error-5')).toHaveTextContent(
      /body must not be blank/i,
    )
    expect(screen.getByTestId('add-note-form-5')).toBeInTheDocument()
  })

  it('cancel closes the form without calling the API', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    render(<AddNoteForm applicationId={5} studentId={42} />)
    await userEvent.click(screen.getByTestId('add-note-open-5'))
    await userEvent.type(screen.getByTestId('add-note-body-5'), 'Will be discarded.')
    await userEvent.click(screen.getByTestId('add-note-cancel-5'))

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByTestId('add-note-form-5')).not.toBeInTheDocument()
    expect(screen.getByTestId('add-note-open-5')).toBeInTheDocument()
  })
})
