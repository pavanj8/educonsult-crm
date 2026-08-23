import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ApplicationNotes from './ApplicationNotes'

describe('ApplicationNotes', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the notes thread for the given application', async () => {
    globalThis.fetch = vi.fn().mockImplementation(async (url: RequestInfo | URL) => {
      const path = String(url)
      if (path.includes('/notes')) {
        return { ok: true, status: 200, json: async () => [] } as Response
      }
      throw new Error(`Unhandled fetch: ${path}`)
    }) as unknown as typeof fetch

    render(<ApplicationNotes applicationId={5} studentId={42} currentUserId={7} />)
    expect(await screen.findByTestId('application-notes-5')).toBeInTheDocument()
    expect(screen.getByTestId('notes-empty-5')).toBeInTheDocument()
  })

  it('hides the add-note form when readOnly is set', async () => {
    globalThis.fetch = vi.fn().mockImplementation(async (url: RequestInfo | URL) => {
      const path = String(url)
      if (path.includes('/notes')) {
        return { ok: true, status: 200, json: async () => [] } as Response
      }
      throw new Error(`Unhandled fetch: ${path}`)
    }) as unknown as typeof fetch

    render(
      <ApplicationNotes
        applicationId={5}
        studentId={42}
        currentUserId={7}
        readOnly
      />,
    )
    expect(await screen.findByTestId('application-notes-5')).toBeInTheDocument()
    expect(screen.queryByTestId('add-note-open-5')).not.toBeInTheDocument()
  })
})
