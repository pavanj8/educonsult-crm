import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import VisaProcessorDashboardPage from './VisaProcessorDashboardPage'

const mockVisaProcessor = {
  id: 91,
  email: 'visa@demo.test',
  role: 'visa_processor' as const,
  tenant_id: 10,
  branch_id: null,
}

const mockApplication = {
  id: 101,
  tenant_id: 10,
  branch_id: 1,
  student_id: 42,
  assigned_counselor_id: 7,
  university_id: 5,
  program_id: 11,
  stage: 'visa_processing',
  created_at: '2026-02-01T10:00:00Z',
  updated_at: '2026-02-02T10:00:00Z',
}

type Handlers = { queueStatus?: number; items?: unknown[]; total?: number }

function createFetchMock(handlers: Handlers = {}) {
  return vi.fn(async (url: RequestInfo | URL) => {
    const path = String(url)
    if (path.includes('/auth/me')) {
      return { ok: true, status: 200, json: async () => mockVisaProcessor }
    }
    if (path.includes('/applications/queue')) {
      if (handlers.queueStatus && handlers.queueStatus >= 400) {
        return { ok: false, status: handlers.queueStatus, json: async () => ({ detail: 'nope' }) }
      }
      const items = handlers.items ?? [mockApplication]
      return { ok: true, status: 200, json: async () => ({ items, total: handlers.total ?? items.length, limit: 50, offset: 0 }) }
    }
    throw new Error(`Unhandled fetch: ${path}`)
  }) as unknown as typeof fetch
}

function renderPage() {
  return render(
    <AuthProvider>
      <VisaProcessorDashboardPage />
    </AuthProvider>,
  )
}

describe('VisaProcessorDashboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders the visa-stage applications queue with a row per application', async () => {
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-table')).toBeInTheDocument()
    expect(screen.getByTestId('visa-queue-row-101')).toBeInTheDocument()
    expect(screen.getByTestId('visa-queue-count')).toHaveTextContent(
      '1 application at the visa stage',
    )
  })

  it('shows the singular form when total is 1', async () => {
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-count')).toHaveTextContent('application')
  })

  it('shows the plural form when total is greater than 1', async () => {
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 3 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-count')).toHaveTextContent(
      '3 applications at the visa stage',
    )
  })

  it('shows an empty state when there are no applications at the visa stage', async () => {
    globalThis.fetch = createFetchMock({ items: [], total: 0 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('visa-queue-table')).not.toBeInTheDocument()
  })

  it('shows a permission error when the API returns 403', async () => {
    globalThis.fetch = createFetchMock({ queueStatus: 403 })
    renderPage()

    const alert = await screen.findByTestId('visa-queue-error')
    expect(alert).toHaveAttribute('role', 'alert')
    expect(alert).toHaveTextContent(/permission/i)
  })

  it('shows a generic error when the API fails with 500', async () => {
    globalThis.fetch = createFetchMock({ queueStatus: 500 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-error')).toHaveTextContent(/failed to load/i)
  })
})
