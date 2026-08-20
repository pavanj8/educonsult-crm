import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StudentDashboardPage from './StudentDashboardPage'

const mockApplications = [
  {
    id: 1,
    tenant_id: 10,
    student_id: 42,
    university_id: 1,
    program_id: 10,
    stage: 'registered' as const,
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 2,
    tenant_id: 10,
    student_id: 42,
    university_id: 2,
    program_id: 20,
    stage: 'document_verification' as const,
    created_at: '2026-02-01T10:00:00Z',
    updated_at: '2026-02-02T10:00:00Z',
  },
]

describe('StudentDashboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders application list after loading', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockApplications,
    }) as typeof fetch

    render(<StudentDashboardPage />)

    await waitFor(() => {
      expect(screen.getByTestId('application-table')).toBeInTheDocument()
    })

    expect(screen.getByText('University of Toronto')).toBeInTheDocument()
    expect(screen.getByText('MSc Computer Science')).toBeInTheDocument()
    expect(screen.getByText('University of Melbourne')).toBeInTheDocument()
    expect(screen.getByText('Master of Engineering')).toBeInTheDocument()
    expect(screen.getByTestId('application-stage-1')).toHaveTextContent('Registered')
    expect(screen.getByTestId('application-stage-2')).toHaveTextContent('Document Verification')
  })

  it('shows empty state when no applications exist', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    }) as typeof fetch

    render(<StudentDashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('No applications yet.')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('application-table')).not.toBeInTheDocument()
  })

  it('shows error state when fetch fails', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    render(<StudentDashboardPage />)

    await waitFor(() => {
      expect(
        screen.getByText('You do not have permission to view applications'),
      ).toBeInTheDocument()
    })
  })

  it('shows independent stage per application row', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockApplications,
    }) as typeof fetch

    render(<StudentDashboardPage />)

    await waitFor(() => {
      expect(screen.getByTestId('application-row-1')).toBeInTheDocument()
    })

    expect(screen.getByTestId('application-stage-1')).toHaveTextContent('Registered')
    expect(screen.getByTestId('application-stage-2')).toHaveTextContent('Document Verification')
  })
})
