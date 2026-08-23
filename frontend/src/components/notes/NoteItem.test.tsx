import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import NoteItem from './NoteItem'
import type { Note } from '../../types/note'

const authorNote: Note = {
  id: 1,
  tenant_id: 10,
  student_id: 42,
  application_id: 5,
  author_user_id: 7,
  body: 'Counselor note.',
  created_at: '2026-04-01T09:00:00Z',
  updated_at: '2026-04-01T09:00:00Z',
}

const peerNote: Note = {
  ...authorNote,
  id: 2,
  author_user_id: 8,
  body: 'Peer-authored note.',
}

describe('NoteItem', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the note body, author, and timestamp', () => {
    render(<NoteItem note={authorNote} currentUserId={7} />)
    expect(screen.getByTestId('note-body-1')).toHaveTextContent('Counselor note.')
    expect(screen.getByTestId('note-meta-1')).toHaveTextContent('Staff #7')
  })

  it('shows Edit / Delete for the author', () => {
    render(<NoteItem note={authorNote} currentUserId={7} />)
    expect(screen.getByTestId('note-actions-1')).toBeInTheDocument()
    expect(screen.getByTestId('note-edit-button-1')).toBeInTheDocument()
    expect(screen.getByTestId('note-delete-button-1')).toBeInTheDocument()
  })

  it('hides Edit / Delete for a non-author', () => {
    render(<NoteItem note={peerNote} currentUserId={7} />)
    expect(screen.queryByTestId('note-actions-2')).not.toBeInTheDocument()
    expect(screen.queryByTestId('note-edit-button-2')).not.toBeInTheDocument()
    expect(screen.queryByTestId('note-delete-button-2')).not.toBeInTheDocument()
  })

  it('opens an edit form when the author clicks Edit', async () => {
    render(<NoteItem note={authorNote} currentUserId={7} />)
    await userEvent.click(screen.getByTestId('note-edit-button-1'))
    expect(screen.getByTestId('note-edit-form-1')).toBeInTheDocument()
    expect(
      (screen.getByTestId('note-edit-body-1') as HTMLTextAreaElement).value,
    ).toBe('Counselor note.')
  })

  it('saves an edited body via PATCH and closes the form on success', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        ...authorNote,
        body: 'Edited body.',
        updated_at: '2026-04-02T09:00:00Z',
      }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<NoteItem note={authorNote} currentUserId={7} />)
    await userEvent.click(screen.getByTestId('note-edit-button-1'))
    await userEvent.clear(screen.getByTestId('note-edit-body-1'))
    await userEvent.type(screen.getByTestId('note-edit-body-1'), 'Edited body.')
    await userEvent.click(screen.getByTestId('note-edit-save-1'))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined]
    expect(url).toContain('/notes/1')
    expect(init?.method).toBe('PATCH')
    const body = JSON.parse((init?.body ?? '{}') as string)
    expect(body).toEqual({ body: 'Edited body.' })

    expect(screen.queryByTestId('note-edit-form-1')).not.toBeInTheDocument()
  })

  it('cancels the edit without calling the API', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    render(<NoteItem note={authorNote} currentUserId={7} />)
    await userEvent.click(screen.getByTestId('note-edit-button-1'))
    await userEvent.click(screen.getByTestId('note-edit-cancel-1'))

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByTestId('note-edit-form-1')).not.toBeInTheDocument()
    expect(screen.getByTestId('note-body-1')).toBeInTheDocument()
  })

  it('deletes a note via DELETE when the author clicks Delete', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => undefined,
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<NoteItem note={authorNote} currentUserId={7} />)
    await userEvent.click(screen.getByTestId('note-delete-button-1'))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined]
    expect(url).toContain('/notes/1')
    expect(init?.method).toBe('DELETE')
  })

  it('renders a "(edited)" marker when updated_at differs from created_at', () => {
    const editedNote: Note = {
      ...authorNote,
      created_at: '2026-04-01T09:00:00Z',
      updated_at: '2026-04-02T09:00:00Z',
    }
    render(<NoteItem note={editedNote} currentUserId={7} />)
    expect(screen.getByTestId('note-meta-1')).toHaveTextContent(/\(edited\)/)
  })

  it('shows a delete error when the backend rejects the delete', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Only the note\'s author may delete it' }),
    }) as typeof fetch

    render(<NoteItem note={authorNote} currentUserId={7} />)
    await userEvent.click(screen.getByTestId('note-delete-button-1'))

    expect(await screen.findByTestId('note-delete-error-1')).toHaveTextContent(
      /permission|may delete/i,
    )
  })

  it('shows an edit error when the backend rejects the edit', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Only the note\'s author may edit it' }),
    }) as typeof fetch

    render(<NoteItem note={authorNote} currentUserId={7} />)
    await userEvent.click(screen.getByTestId('note-edit-button-1'))
    await userEvent.clear(screen.getByTestId('note-edit-body-1'))
    await userEvent.type(screen.getByTestId('note-edit-body-1'), 'Edited.')
    await userEvent.click(screen.getByTestId('note-edit-save-1'))

    expect(await screen.findByTestId('note-edit-error-1')).toHaveTextContent(
      /permission|may edit/i,
    )
  })
})
