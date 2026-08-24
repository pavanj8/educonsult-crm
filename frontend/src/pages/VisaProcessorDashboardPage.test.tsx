import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
    if (path.includes('/visa/applications/queue')) {
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

  it('shows the backend detail when the API fails with 500', async () => {
    // The visa queue router (#191) translates a database outage into
    // a 503 with a specific detail string. For non-auth failures the
    // hook surfaces whatever the backend's ``detail`` was so the
    // operator can distinguish a transient backend issue from a
    // generic client-side failure.
    globalThis.fetch = createFetchMock({ queueStatus: 500 })
    renderPage()

    const alert = await screen.findByTestId('visa-queue-error')
    expect(alert).toHaveTextContent(/nope/)
  })

  it('triggers a refetch when the Refresh button is clicked', async () => {
    const user = userEvent.setup()
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    await screen.findByTestId('visa-queue-table')

    const refresh = screen.getByRole('button', { name: /refresh/i })
    await user.click(refresh)

    await waitFor(() => {
      const queueCalls = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.filter(
        ([url]) => String(url).includes('/visa/applications/queue'),
      )
      expect(queueCalls.length).toBeGreaterThanOrEqual(2)
    })
  })

  it('renders the unauthenticated state without calling the API', async () => {
    localStorage.removeItem('access_token')
    const fetchMock = createFetchMock()
    globalThis.fetch = fetchMock
    renderPage()

    // The dashboard should not crash; without an access token the
    // hook short-circuits and the dashboard renders its empty
    // loading-resolved state (loading false, no error, no rows).
    await waitFor(() => {
      expect(screen.getByTestId('visa-queue-empty')).toBeInTheDocument()
    })
    expect(
      (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls.filter(([url]) =>
        String(url).includes('/visa/applications/queue'),
      ),
    ).toHaveLength(0)
  })

  it('renders an "Update visa detail" toggle on every row, initially collapsed', async () => {
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    const toggle = await screen.findByTestId('visa-queue-edit-toggle-101')
    expect(toggle).toHaveTextContent(/update visa detail/i)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByTestId('visa-detail-panel-101')).not.toBeInTheDocument()
  })

  it('opens the visa detail update form when the per-row toggle is clicked', async () => {
    const user = userEvent.setup()
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    const toggle = await screen.findByTestId('visa-queue-edit-toggle-101')
    await user.click(toggle)

    const panel = await screen.findByTestId('visa-detail-panel-101')
    expect(panel).toBeInTheDocument()
    // The form mounts and goes through its loading -> empty state
    // (no detail recorded yet -> 404 from fetchVisaDetail). The
    // dashboard wires the form's `onSaved` to close the panel.
    expect(await screen.findByTestId('visa-detail-form-101')).toBeInTheDocument()
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(toggle).toHaveTextContent(/close/i)
  })

  it('closes the visa detail update form when the toggle is clicked a second time', async () => {
    const user = userEvent.setup()
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    const toggle = await screen.findByTestId('visa-queue-edit-toggle-101')
    await user.click(toggle)
    await screen.findByTestId('visa-detail-form-101')

    await user.click(toggle)

    await waitFor(() => {
      expect(screen.queryByTestId('visa-detail-panel-101')).not.toBeInTheDocument()
    })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
  })
})
