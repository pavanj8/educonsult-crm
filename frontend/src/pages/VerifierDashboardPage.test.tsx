import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import VerifierDashboardPage from './VerifierDashboardPage'

const mockVerifier = {
  id: 90,
  email: 'verifier@demo.test',
  role: 'document_verifier' as const,
  tenant_id: 10,
  branch_id: null,
}

const mockDoc = {
  id: 7,
  tenant_id: 10,
  application_id: 3,
  checklist_item_template_id: 2,
  original_filename: 'passport.pdf',
  content_type: 'application/pdf',
  size_bytes: 1024,
  uploaded_by_user_id: 42,
  uploaded_at: '2026-02-01T10:00:00Z',
  application_stage: 'documents',
  student_id: 42,
  university_id: 1,
  program_id: 10,
}

type Handlers = { queueStatus?: number; items?: unknown[]; total?: number }

function createFetchMock(handlers: Handlers = {}) {
  return vi.fn(async (url: RequestInfo | URL) => {
    const path = String(url)
    if (path.includes('/auth/me')) {
      return { ok: true, status: 200, json: async () => mockVerifier }
    }
    if (path.includes('/verifier/documents/pending')) {
      if (handlers.queueStatus && handlers.queueStatus >= 400) {
        return { ok: false, status: handlers.queueStatus, json: async () => ({ detail: 'nope' }) }
      }
      const items = handlers.items ?? [mockDoc]
      return { ok: true, status: 200, json: async () => ({ items, total: handlers.total ?? items.length, limit: 50, offset: 0 }) }
    }
    throw new Error(`Unhandled fetch: ${path}`)
  }) as unknown as typeof fetch
}

function renderPage() {
  return render(
    <AuthProvider>
      <VerifierDashboardPage />
    </AuthProvider>,
  )
}

describe('VerifierDashboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders the pending-document queue with a row per document', async () => {
    globalThis.fetch = createFetchMock({ items: [mockDoc], total: 1 })
    renderPage()

    expect(await screen.findByTestId('verifier-queue-table')).toBeInTheDocument()
    expect(screen.getByTestId('verifier-queue-row-7')).toHaveTextContent('passport.pdf')
    expect(screen.getByTestId('verifier-queue-count')).toHaveTextContent('1 document pending verification')
  })

  it('shows an empty state when there are no pending documents', async () => {
    globalThis.fetch = createFetchMock({ items: [], total: 0 })
    renderPage()

    expect(await screen.findByTestId('verifier-queue-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('verifier-queue-table')).not.toBeInTheDocument()
  })

  it('shows a permission error when the API returns 403', async () => {
    globalThis.fetch = createFetchMock({ queueStatus: 403 })
    renderPage()

    const alert = await screen.findByTestId('verifier-queue-error')
    expect(alert).toHaveAttribute('role', 'alert')
    expect(alert).toHaveTextContent(/permission/i)
  })

  it('shows a generic error when the API fails with 500', async () => {
    globalThis.fetch = createFetchMock({ queueStatus: 500 })
    renderPage()

    expect(await screen.findByTestId('verifier-queue-error')).toHaveTextContent(/failed to load/i)
  })
})
