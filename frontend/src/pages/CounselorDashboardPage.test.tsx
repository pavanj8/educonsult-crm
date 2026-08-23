import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import CounselorDashboardPage from './CounselorDashboardPage'

const mockCounselor = { id: 7, email: 'c@t.test', role: 'counselor' as const, tenant_id: 10, branch_id: 1 }
const mockApp = { id: 5, tenant_id: 10, branch_id: 1, student_id: 42, assigned_counselor_id: 7, university_id: 1, program_id: 2, stage: 'registered', created_at: '2026-02-01T10:00:00Z', updated_at: '2026-02-01T10:00:00Z' }

function createFetchMock(handlers: { status?: number; apps?: unknown[] } = {}) {
  return vi.fn(async (url: RequestInfo | URL) => {
    const path = String(url)
    if (path.includes('/auth/me')) {
      return { ok: true, status: 200, json: async () => mockCounselor }
    }
    if (path.includes('/applications/assigned-to-me')) {
      if (handlers.status && handlers.status >= 400) {
        return { ok: false, status: handlers.status, json: async () => ({ detail: 'no' }) }
      }
      return { ok: true, status: 200, json: async () => handlers.apps ?? [mockApp] }
    }
    // The counselor dashboard embeds the E22 meeting widget per row;
    // tests that care about meeting state inject their own mock. The
    // default mock returns an empty list so the existing assertions
    // continue to focus on the assigned-application queue behaviour.
    if (/\/applications\/\d+\/meetings(\?|$)/.test(path)) {
      return { ok: true, status: 200, json: async () => [] }
    }
    // The counselor dashboard also embeds the E24 notes thread widget
    // (ticket #166); the default mock returns an empty list so the
    // queue behaviour assertions continue to dominate.
    if (path.includes('/notes')) {
      return { ok: true, status: 200, json: async () => [] }
    }
    throw new Error(`Unhandled fetch: ${path}`)
  }) as unknown as typeof fetch
}

function renderPage() {
  return render(
    <AuthProvider>
      <CounselorDashboardPage />
    </AuthProvider>,
  )
}

describe('CounselorDashboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders the assigned-application queue', async () => {
    globalThis.fetch = createFetchMock({ apps: [mockApp] })
    renderPage()
    expect(await screen.findByTestId('counselor-queue-table')).toBeInTheDocument()
    expect(screen.getByTestId('counselor-queue-row-5')).toHaveTextContent('#42')
  })

  it('shows the empty state when nothing is assigned', async () => {
    globalThis.fetch = createFetchMock({ apps: [] })
    renderPage()
    expect(await screen.findByTestId('counselor-queue-empty')).toBeInTheDocument()
  })

  it('shows a permission error on 403', async () => {
    globalThis.fetch = createFetchMock({ status: 403 })
    renderPage()
    const alert = await screen.findByTestId('counselor-queue-error')
    expect(alert).toHaveAttribute('role', 'alert')
    expect(alert).toHaveTextContent(/permission/i)
  })
})
