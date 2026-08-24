import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApplicationRow from './ApplicationRow'
import type { Application } from '../../types/application'

const mockApplication: Application = {
  id: 7,
  tenant_id: 10,
  student_id: 42,
  university_id: 1,
  program_id: 10,
  stage: 'document_verification',
  loan_opt_in: false,
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

const mockChecklistResponse = {
  applicationId: 7,
  items: [
    {
      templateId: 10,
      stage: 'document_verification',
      name: 'Passport',
      description: null,
      required: true,
      orderIndex: 0,
      upload: null,
    },
  ],
}

function renderRow(props: Partial<React.ComponentProps<typeof ApplicationRow>> = {}) {
  const defaultProps: React.ComponentProps<typeof ApplicationRow> = {
    application: mockApplication,
    universityName: 'University of Toronto',
    programName: 'MSc Computer Science',
    createdAt: '2026-01-15T10:00:00Z',
  }
  return render(
    <table>
      <tbody>
        <ApplicationRow {...defaultProps} {...props} />
      </tbody>
    </table>,
  )
}

describe('ApplicationRow', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders the application summary columns and a View checklist toggle', () => {
    globalThis.fetch = vi.fn() as typeof fetch

    renderRow()

    expect(screen.getByTestId('application-row-7')).toBeInTheDocument()
    expect(screen.getByTestId('application-stage-7')).toHaveTextContent('Document Verification')
    expect(screen.getByText('University of Toronto')).toBeInTheDocument()
    expect(screen.getByText('MSc Computer Science')).toBeInTheDocument()
    expect(
      screen.getByTestId('application-checklist-toggle-7'),
    ).toHaveTextContent('View checklist')
    expect(screen.getByTestId('application-checklist-toggle-7')).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('does not fetch the checklist until the row is expanded', () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    renderRow()

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetches the checklist and renders it when the toggle is clicked', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockChecklistResponse,
    }) as typeof fetch

    renderRow()

    await user.click(screen.getByTestId('application-checklist-toggle-7'))

    expect(
      screen.getByTestId('application-checklist-toggle-7'),
    ).toHaveTextContent('Hide checklist')
    expect(screen.getByTestId('application-checklist-toggle-7')).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(screen.getByTestId('checklist-view-7')).toBeInTheDocument()
    expect(screen.getByTestId('application-checklist-row-7')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByTestId('checklist-item-10')).toBeInTheDocument()
    })

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/applications/7/checklist',
      expect.any(Object),
    )
  })

  it('collapses the row and clears the rendered checklist when toggled closed', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockChecklistResponse,
    }) as typeof fetch

    renderRow()

    await user.click(screen.getByTestId('application-checklist-toggle-7'))
    expect(screen.getByTestId('checklist-view-7')).toBeInTheDocument()

    await user.click(screen.getByTestId('application-checklist-toggle-7'))

    expect(screen.queryByTestId('checklist-view-7')).not.toBeInTheDocument()
    expect(
      screen.getByTestId('application-checklist-toggle-7'),
    ).toHaveTextContent('View checklist')
    expect(screen.getByTestId('application-checklist-toggle-7')).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('renders an empty program cell when programName is null', () => {
    globalThis.fetch = vi.fn() as typeof fetch

    renderRow({ programName: null })

    // The program cell should still be present but empty. The fallback
    // to `Program #N` lives in the parent (StudentDashboardPage), not here.
    const programCells = screen
      .getAllByRole('cell')
      .filter((cell) => cell.textContent?.trim() === '')
    expect(programCells.length).toBeGreaterThanOrEqual(1)
  })

  it('formats the created date for human display', () => {
    globalThis.fetch = vi.fn() as typeof fetch

    renderRow({ createdAt: '2026-01-15T10:00:00Z' })

    // toLocaleDateString output varies by environment; assert that some
    // year fragment is present and the raw ISO string is not shown as-is.
    expect(screen.getByText(/2026/)).toBeInTheDocument()
    expect(screen.queryByText('2026-01-15T10:00:00Z')).not.toBeInTheDocument()
  })
})