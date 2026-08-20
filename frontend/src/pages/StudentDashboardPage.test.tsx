import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import StudentDashboardPage from './StudentDashboardPage'

const mockStudent = {
  id: 8,
  email: 'student@demo.test',
  role: 'student' as const,
  tenant_id: 10,
  branch_id: 1,
}

const mockApplication = {
  id: 1,
  tenant_id: 10,
  student_id: 8,
  university_id: 1,
  program_id: 10,
  stage: 'registered' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function renderStudentDashboard() {
  return render(
    <AuthProvider>
      <StudentDashboardPage />
    </AuthProvider>,
  )
}

describe('StudentDashboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStudent,
    }) as typeof fetch
  })

  it('renders the new application form', async () => {
    renderStudentDashboard()

    expect(await screen.findByTestId('student-dashboard-page')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Student dashboard' })).toBeInTheDocument()
    expect(screen.getByTestId('application-university')).toBeInTheDocument()
    expect(screen.getByTestId('application-program')).toBeInTheDocument()
    expect(screen.getByTestId('application-submit')).toBeInTheDocument()
    expect(screen.getByTestId('application-program')).toBeDisabled()
  })

  it('enables program select after choosing a university', async () => {
    const user = userEvent.setup()
    renderStudentDashboard()

    await screen.findByTestId('application-university')
    await user.selectOptions(screen.getByTestId('application-university'), '1')

    expect(screen.getByTestId('application-program')).not.toBeDisabled()
    expect(screen.getByRole('option', { name: 'MSc Computer Science' })).toBeInTheDocument()
  })

  it('creates an application and shows success message', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockStudent,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockApplication,
      }) as typeof fetch

    renderStudentDashboard()

    await screen.findByTestId('application-university')
    await user.selectOptions(screen.getByTestId('application-university'), '1')
    await user.selectOptions(screen.getByTestId('application-program'), '10')
    await user.click(screen.getByTestId('application-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('application-success')).toHaveTextContent(
        /Application created for MSc Computer Science at University of Toronto/i,
      )
    })

    expect(globalThis.fetch).toHaveBeenCalledWith('/applications', {
      method: 'POST',
      body: JSON.stringify({ university_id: 1, program_id: 10 }),
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-token',
      },
    })
  })

  it('shows API error when creation fails', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockStudent,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Insufficient permissions' }),
      }) as typeof fetch

    renderStudentDashboard()

    await screen.findByTestId('application-university')
    await user.selectOptions(screen.getByTestId('application-university'), '1')
    await user.selectOptions(screen.getByTestId('application-program'), '10')
    await user.click(screen.getByTestId('application-submit'))

    expect(await screen.findByTestId('application-error')).toHaveTextContent(
      'Insufficient permissions',
    )
  })
})
